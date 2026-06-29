"""
海外公司财务与历史 PE 采集器。
设计原则：
  - 每个 ticker 只拉一次 yfinance，处理所有 pending 任务。
  - 失败任务指数退避，可中断后恢复。
  - 所有财务数据统一换算为美元；存储单位保持 亿美元。
"""
import logging
import time
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

from database import SessionLocal
from models import Company, Financial, OverseasFinancialUpdate, CompanyValuationSnapshot
from overseas_tickers import is_overseas_ticker, to_yfinance_symbol
from fx_rates import get_fx_rate

logger = logging.getLogger(__name__)

YFINANCE_DELAY_SECONDS = 10.0
TICKERS_PER_RUN = 2
MAX_RETRIES = 5

SNAPSHOT_PE_DATES = [date(2024, 12, 31), date(2025, 12, 31)]


def _yf_obj(ticker: str):
    if not HAS_YFINANCE:
        raise RuntimeError("yfinance not installed")
    return yf.Ticker(to_yfinance_symbol(ticker))


def _find_hist_price(hist: pd.DataFrame, target: date) -> Optional[float]:
    if hist is None or hist.empty:
        return None
    try:
        row = hist.loc[:target.strftime("%Y-%m-%d")].iloc[-1]
        return float(row["Close"])
    except Exception:
        return None


def _sum_quarters(df: Optional[pd.DataFrame], target_date: date, row_name: str) -> Optional[float]:
    if df is None or df.empty:
        return None
    try:
        if row_name not in df.index:
            return None
        cols = [c for c in df.columns if pd.to_datetime(c).date() <= target_date]
        cols = sorted(cols, key=lambda c: pd.to_datetime(c).date())[-4:]
        if not cols:
            return None
        total = df.loc[row_name, cols].sum()
        return float(total) if pd.notna(total) else None
    except Exception as e:
        logger.debug(f"_sum_quarters failed: {e}")
        return None


def _annual_value(df: Optional[pd.DataFrame], fiscal_year: int, row_name: str) -> Optional[float]:
    if df is None or df.empty:
        return None
    try:
        if row_name not in df.index:
            return None
        for c in df.columns:
            d = pd.to_datetime(c).date()
            if d.year == fiscal_year:
                return float(df.loc[row_name, c])
        return None
    except Exception as e:
        logger.debug(f"_annual_value failed: {e}")
        return None


def _lookup_rate(db, currency: str, for_date: date) -> Optional[float]:
    if currency == "USD":
        return 1.0
    return get_fx_rate(db, currency, for_date)


def _to_billion_usd(raw_local: Optional[float], fx_rate: Optional[float]) -> Optional[float]:
    if raw_local is None or fx_rate is None or fx_rate <= 0:
        return None
    return round((raw_local / fx_rate) / 1e8, 2)


REVENUE_ROWS = ["Total Revenue", "Revenue", "TotalRevenue"]
NET_INCOME_ROWS = ["Net Income", "NetIncome", "Net Income Common Stockholders"]


def _first_row(df: Optional[pd.DataFrame], names: list[str]) -> Optional[str]:
    if df is None:
        return None
    for n in names:
        if n in df.index:
            return n
    return None


def _annual_income(df: Optional[pd.DataFrame], fiscal_year: int) -> tuple[Optional[float], Optional[float], Optional[date]]:
    rev_row = _first_row(df, REVENUE_ROWS)
    ni_row = _first_row(df, NET_INCOME_ROWS)
    if not rev_row or not ni_row:
        return None, None, None
    for c in df.columns:
        d = pd.to_datetime(c).date()
        if d.year == fiscal_year:
            rev_val = df.loc[rev_row, c]
            ni_val = df.loc[ni_row, c]
            rev = float(rev_val) if rev_row in df.index and pd.notna(rev_val) else None
            ni = float(ni_val) if ni_row in df.index and pd.notna(ni_val) else None
            return rev, ni, d
    return None, None, None


def update_financial(db, ticker: str, company_id: int, task: str,
                     info: dict, annual: Optional[pd.DataFrame],
                     quarterly: Optional[pd.DataFrame]) -> bool:
    """task is fy:YYYY or ttm:YYYY. Returns True on success."""
    kind, year_str = task.split(":")
    year = int(year_str)

    fin_currency = info.get("financialCurrency") or info.get("currency") or "USD"

    if kind == "fy":
        rev, ni, period_end = _annual_income(annual, year)
    else:  # ttm
        period_end = date.today()
        if quarterly is not None and not quarterly.empty:
            period_end = max(pd.to_datetime(c).date() for c in quarterly.columns)
        rev = _sum_quarters(quarterly, period_end, _first_row(quarterly, REVENUE_ROWS) or "")
        ni = _sum_quarters(quarterly, period_end, _first_row(quarterly, NET_INCOME_ROWS) or "")

    if rev is None and ni is None:
        logger.warning(f"{ticker} {task}: no revenue/net income available")
        return False

    fx_rate = _lookup_rate(db, fin_currency, period_end or date.today())
    if fx_rate is None:
        logger.warning(f"{ticker} {task}: no FX rate for {fin_currency}")
        return False

    existing = db.query(Financial).filter(
        Financial.company_id == company_id,
        Financial.fiscal_year == year,
    ).first()

    data_source = "yfinance_ttm" if kind == "ttm" else "yfinance"

    if existing:
        existing.revenue = _to_billion_usd(rev, fx_rate)
        existing.net_income = _to_billion_usd(ni, fx_rate)
        existing.currency = fin_currency
        existing.fx_rate = fx_rate
        existing.original_revenue = rev
        existing.original_net_income = ni
        existing.data_source = data_source
        existing.last_verified = date.today()
    else:
        db.add(Financial(
            company_id=company_id,
            fiscal_year=year,
            revenue=_to_billion_usd(rev, fx_rate),
            net_income=_to_billion_usd(ni, fx_rate),
            currency=fin_currency,
            fx_rate=fx_rate,
            original_revenue=rev,
            original_net_income=ni,
            data_source=data_source,
            last_verified=date.today(),
        ))
    db.commit()
    logger.info(f"{ticker} {task}: rev={_to_billion_usd(rev, fx_rate)}, ni={_to_billion_usd(ni, fx_rate)}")
    return True


def _last_trading_date(hist: pd.DataFrame, target: date) -> Optional[date]:
    if hist is None or hist.empty:
        return None
    try:
        ts = hist.loc[:target.strftime("%Y-%m-%d")]
        if ts.empty:
            return None
        d = ts.index[-1]
        return d.date() if hasattr(d, "date") else pd.to_datetime(d).date()
    except Exception:
        return None


def update_pe_snapshot(db, ticker: str, company_id: int, task: str,
                       info: dict, hist: Optional[pd.DataFrame],
                       quarterly: Optional[pd.DataFrame]) -> bool:
    """task is pe:YYYY-MM-DD or pe:latest."""
    _, date_part = task.split(":", 1)
    if date_part == "latest":
        target = _last_trading_date(hist, date.today()) or date.today()
    else:
        target = datetime.strptime(date_part, "%Y-%m-%d").date()

    price_local = _find_hist_price(hist, target)
    if price_local is None:
        logger.warning(f"{ticker} {task}: no price for {target}")
        return False

    price_currency = info.get("currency") or info.get("financialCurrency") or "USD"
    shares = info.get("sharesOutstanding")
    if not shares:
        logger.warning(f"{ticker} {task}: no sharesOutstanding")
        return False

    eps_local = info.get("trailingEps")
    if eps_local is None and quarterly is not None:
        ni_row = _first_row(quarterly, NET_INCOME_ROWS)
        if ni_row:
            ttm_ni_local = _sum_quarters(quarterly, target, ni_row)
            if ttm_ni_local:
                eps_local = ttm_ni_local / shares

    if eps_local is None or eps_local == 0:
        logger.warning(f"{ticker} {task}: cannot compute EPS")
        return False

    pe = round(price_local / eps_local, 2)

    fx_rate = _lookup_rate(db, price_currency, target)
    if fx_rate is None:
        logger.warning(f"{ticker} {task}: no FX rate for {price_currency}")
        return False
    price_usd = price_local / fx_rate
    market_cap_b = round((price_usd * shares) / 1e8, 2)

    existing = db.query(CompanyValuationSnapshot).filter(
        CompanyValuationSnapshot.company_id == company_id,
        CompanyValuationSnapshot.snapshot_date == target,
    ).first()

    if existing:
        existing.price_usd = round(price_usd, 4)
        existing.eps_ttm = round(eps_local, 4)
        existing.pe_ttm = pe
        existing.market_cap_b = market_cap_b
        existing.price_currency = price_currency
        existing.fx_rate = fx_rate
        existing.source = "yfinance"
    else:
        db.add(CompanyValuationSnapshot(
            company_id=company_id,
            snapshot_date=target,
            price_usd=round(price_usd, 4),
            eps_ttm=round(eps_local, 4),
            pe_ttm=pe,
            market_cap_b=market_cap_b,
            price_currency=price_currency,
            fx_rate=fx_rate,
            source="yfinance",
        ))
    db.commit()
    logger.info(f"{ticker} {task}: pe={pe} @ {target} price={price_usd:.2f}USD")
    return True


def ensure_tasks(db):
    """为每个海外 ticker 创建所有待处理任务（幂等，按 ticker 去重）。"""
    # 同 ticker 多公司（GOOGL/INTC/SMSN）的多个业务部门共享同一份任务表 —
    # 用 set 去重避免重复插入；后续 run_next_batch 按 .distinct() 取 ticker，已经天然去重。
    seen_tickers: set[str] = set()
    created = 0
    companies = db.query(Company).filter(Company.ticker.isnot(None)).all()
    for co in companies:
        t = (co.ticker or "").upper().strip()
        if not is_overseas_ticker(t) or t in seen_tickers:
            continue
        seen_tickers.add(t)
        tasks = ["fy:2024", "fy:2025", "ttm:2026"]
        for d in SNAPSHOT_PE_DATES:
            tasks.append(f"pe:{d.isoformat()}")
        tasks.append("pe:latest")
        for task in tasks:
            exists = db.query(OverseasFinancialUpdate).filter(
                OverseasFinancialUpdate.ticker == t,
                OverseasFinancialUpdate.task == task,
            ).first()
            if not exists:
                db.add(OverseasFinancialUpdate(ticker=t, task=task, status="pending"))
                created += 1
    db.commit()
    logger.info(f"ensure_tasks: created {created} tasks for {len(seen_tickers)} unique tickers")
    return created


def _is_rate_limit(error: Optional[str]) -> bool:
    if not error:
        return False
    lowered = error.lower()
    return any(k in lowered for k in ["too many requests", "rate limited", "429", "rate limit"])


def _record_result(db, rec: OverseasFinancialUpdate, success: bool, error: Optional[str]):
    now = datetime.utcnow()
    rec.last_attempt = now
    if success:
        rec.status = "success"
        rec.error_count = 0
        rec.last_error = None
        rec.next_attempt = None
    else:
        rec.error_count += 1
        rec.last_error = (error or "unknown")[:500]
        # 限流错误绝不永久失败（yfinance 是按 IP 限流，6h 后大概率降级），
        # 上限封顶到 24h 不让 backoff 无限增长；其他错误按 2^n 指数退避，
        # MAX_RETRIES 次后状态置为 failed（交给 reset_rate_limited_backoff 工具）。
        if _is_rate_limit(error):
            rec.status = "pending"
            hours = min(6 * rec.error_count, 24)
            rec.next_attempt = now + timedelta(hours=hours)
        else:
            if rec.error_count >= MAX_RETRIES:
                rec.status = "failed"
                rec.next_attempt = None
            else:
                rec.status = "pending"
                rec.next_attempt = now + timedelta(hours=2 ** rec.error_count)
    db.commit()


def run_next_batch(db, tickers_per_run: int = TICKERS_PER_RUN) -> dict:
    """处理下一批 pending 的 ticker，返回统计。

    共享 IP：批内任一 ticker 撞 yfinance 429，整批剩余 ticker 也推到 6h 后再试。
    避免明知被 ban 还继续触发请求，浪费预算。
    """
    now = datetime.utcnow()
    pending_tickers = (
        db.query(OverseasFinancialUpdate.ticker)
        .filter(
            OverseasFinancialUpdate.status.in_(["pending"]),
            (OverseasFinancialUpdate.next_attempt.is_(None)) |
            (OverseasFinancialUpdate.next_attempt <= now)
        )
        .distinct()
        .limit(tickers_per_run)
        .all()
    )
    tickers = [r[0] for r in pending_tickers]
    if not tickers:
        return {"processed": 0, "success": 0, "failed": 0, "rate_limited": 0}

    stats = {"processed": 0, "success": 0, "failed": 0, "rate_limited": 0}
    # 整批共享同一出口 IP，任一 ticker 撞 429 后整批放弃，避免向已被 ban 的 IP 继续打
    rate_limited = False

    for ticker in tickers:
        if rate_limited:
            logger.warning(f"run_next_batch: skipping {ticker} (prior 429 in batch)")
            _defer_pending_tickers(db, [ticker], hours=6)
            stats["rate_limited"] += 1
            continue

        stats["processed"] += 1
        try:
            company = db.query(Company).filter(
                Company.ticker.ilike(ticker)
            ).first()
            if not company:
                _skip_all(db, ticker, "no company")
                stats["failed"] += 1
                continue

            tasks = db.query(OverseasFinancialUpdate).filter(
                OverseasFinancialUpdate.ticker == ticker,
                OverseasFinancialUpdate.status == "pending",
                (OverseasFinancialUpdate.next_attempt.is_(None)) |
                (OverseasFinancialUpdate.next_attempt <= now)
            ).order_by(OverseasFinancialUpdate.id).all()

            yfo = _yf_obj(ticker)
            info = yfo.info or {}
            time.sleep(2)

            # Determine which yfinance data we actually need for pending tasks
            pending_task_names = {t.task for t in tasks}
            needs_financials = any(t.startswith("fy:") or t.startswith("ttm:") for t in pending_task_names)
            needs_pe = any(t.startswith("pe:") for t in pending_task_names)

            annual = yfo.income_stmt if needs_financials else None
            if needs_financials:
                time.sleep(2)
            quarterly = yfo.quarterly_income_stmt if (needs_financials or needs_pe) else None
            if needs_financials or needs_pe:
                time.sleep(2)
            hist = yfo.history(period="3y") if needs_pe else None

            for task_rec in tasks:
                try:
                    if task_rec.task.startswith("fy:") or task_rec.task.startswith("ttm:"):
                        ok = update_financial(db, ticker, company.id, task_rec.task,
                                              info, annual, quarterly)
                    else:
                        ok = update_pe_snapshot(db, ticker, company.id, task_rec.task,
                                                info, hist, quarterly)
                    _record_result(db, task_rec, ok, None)
                    if ok:
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1
                except Exception as e:
                    err_str = str(e)
                    _record_result(db, task_rec, False, err_str)
                    stats["failed"] += 1
                    if _is_rate_limit(err_str):
                        rate_limited = True

            time.sleep(YFINANCE_DELAY_SECONDS)
        except Exception as e:
            logger.error(f"Batch processing failed for {ticker}: {e}")
            err = str(e)
            if _is_rate_limit(err):
                rate_limited = True
            for rec in db.query(OverseasFinancialUpdate).filter_by(ticker=ticker, status="pending").all():
                _record_result(db, rec, False, err)
            stats["failed"] += 1

    logger.info(f"run_next_batch: {stats}")
    return stats


def _defer_pending_tickers(db, tickers: list[str], hours: int = 6) -> int:
    """批量把一组 ticker 的 pending 任务统一推迟到 t+N hours。

    用于：整批已被 yfinance 限流，把还没轮到的 ticker 直接延后，
    节省本来要浪费的 yfinance 调用配额。

    不增加 error_count（错误计数应反映真实失败次数，而不是调度原因）。
    """
    if not tickers:
        return 0
    new_attempt = datetime.utcnow() + timedelta(hours=hours)
    pending = db.query(OverseasFinancialUpdate).filter(
        OverseasFinancialUpdate.ticker.in_(tickers),
        OverseasFinancialUpdate.status == "pending",
    ).all()
    for rec in pending:
        rec.next_attempt = new_attempt
    db.commit()
    logger.info(f"_defer_pending_tickers: deferred {len(pending)} tasks across {len(tickers)} tickers to {new_attempt}")
    return len(pending)


def _skip_all(db, ticker, reason):
    for rec in db.query(OverseasFinancialUpdate).filter_by(ticker=ticker, status="pending").all():
        rec.status = "failed"
        rec.last_error = reason[:500]
        rec.last_attempt = datetime.utcnow()
    db.commit()


def reset_rate_limited_backoff(db, hours: int = 6) -> int:
    """把已经被限流标记过的 pending 任务的 next_attempt 统一推迟。

    用于以下场景：
      - 调度策略变更后，把所有仍处于 30 分钟旧退避窗口的任务拉回新的 6 小时窗口；
      - IP 被 yfinance 临时封禁时，把刚被打回去的任务再延后一档，避免雪崩式重试。

    只动 status='pending' 且 error_count > 0 的记录（说明确实撞过限流）；
    status='success' 或 status='failed' 的不碰。
    """
    now = datetime.utcnow()
    new_attempt = now + timedelta(hours=hours)
    pending = db.query(OverseasFinancialUpdate).filter(
        OverseasFinancialUpdate.status == "pending",
        OverseasFinancialUpdate.error_count > 0,
    ).all()
    for rec in pending:
        rec.next_attempt = new_attempt
    db.commit()
    logger.info(f"reset_rate_limited_backoff: {len(pending)} tasks rescheduled to {new_attempt}")
    return len(pending)


if __name__ == "__main__":
    # 一次性 CLI：python -m overseas_financial_collector reset
    import sys
    from database import SessionLocal
    cmd = sys.argv[1] if len(sys.argv) > 1 else "reset"
    db = SessionLocal()
    try:
        if cmd == "reset":
            n = reset_rate_limited_backoff(db)
            print(f"rescheduled {n} rate-limited tasks to t+6h")
        else:
            print(f"unknown command: {cmd}")
            sys.exit(1)
    finally:
        db.close()
