from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch
import pandas as pd

import overseas_financial_collector as ofc
from overseas_financial_collector import (
    update_financial,
    update_pe_snapshot,
    _record_result,
    _defer_pending_tickers,
    ensure_tasks,
    reset_rate_limited_backoff,
    run_next_batch,
)
from models import Financial, CompanyValuationSnapshot, Company, OverseasFinancialUpdate


def _make_info():
    return {
        "financialCurrency": "USD",
        "currency": "USD",
        "sharesOutstanding": 1_000_000_000,
        "trailingEps": 5.0,
    }


def _make_annual():
    return pd.DataFrame(
        {"2024-12-31": [100_000_000_000.0, 20_000_000_000.0]},
        index=["Total Revenue", "Net Income"],
    )


def test_update_financial_writes_usd_billions(db):
    co = db.query(Company).filter_by(ticker="NVDA").first()
    if not co:
        co = Company(name="NVIDIA", name_cn="英伟达", ticker="NVDA", company_type="chip_design", sector="GPU")
        db.add(co); db.flush()

    annual = _make_annual()
    with patch("overseas_financial_collector._lookup_rate", return_value=1.0):
        ok = update_financial(db, "NVDA", co.id, "fy:2024", _make_info(), annual, None)

    assert ok is True
    fin = db.query(Financial).filter_by(company_id=co.id, fiscal_year=2024).first()
    assert fin is not None
    assert fin.revenue == 1000.0       # 100B USD -> 1000 亿 USD
    assert fin.net_income == 200.0
    assert fin.currency == "USD"
    assert fin.data_source == "yfinance"


def test_update_pe_snapshot_writes_snapshot(db):
    co = db.query(Company).filter_by(ticker="NVDA").first()
    if not co:
        co = Company(name="NVIDIA", name_cn="英伟达", ticker="NVDA", company_type="chip_design", sector="GPU")
        db.add(co); db.flush()

    hist = pd.DataFrame(
        {"Close": [150.0]},
        index=pd.to_datetime(["2025-12-31"]),
    )
    with patch("overseas_financial_collector._lookup_rate", return_value=1.0):
        ok = update_pe_snapshot(db, "NVDA", co.id, "pe:2025-12-31",
                                _make_info(), hist, None)

    assert ok is True
    snap = db.query(CompanyValuationSnapshot).filter_by(
        company_id=co.id, snapshot_date=date(2025, 12, 31)
    ).first()
    assert snap is not None
    assert snap.pe_ttm == 30.0         # 150 / 5
    assert snap.market_cap_b == 1500.0   # 150 USD * 1B shares / 1e8


def test_rate_limit_backoff_is_6_hours(db):
    """限流错误应该把 next_attempt 推到 t+6h（首次失败），不是 30 分钟。"""
    rec = OverseasFinancialUpdate(
        ticker="NVDA", task="fy:2024", status="pending",
        error_count=0,
    )
    db.add(rec); db.flush()
    before = datetime.utcnow()
    _record_result(db, rec, success=False, error="HTTPError: Too Many Requests")
    db.refresh(rec)
    assert rec.status == "pending"
    assert rec.error_count == 1
    delta = rec.next_attempt - before
    # 第一次限流：6h ± 5s 容差
    assert timedelta(hours=5, minutes=59, seconds=55) < delta < timedelta(hours=6, seconds=5)


def test_non_rate_limit_error_uses_exponential_backoff(db):
    """非限流的失败（如网络超时）仍然走指数退避 2h,4h,8h…"""
    rec = OverseasFinancialUpdate(
        ticker="AMD", task="fy:2024", status="pending",
        error_count=0,
    )
    db.add(rec); db.flush()
    before = datetime.utcnow()
    _record_result(db, rec, success=False, error="ConnectionResetError: peer closed")
    db.refresh(rec)
    assert rec.status == "pending"
    delta = rec.next_attempt - before
    assert timedelta(hours=1, seconds=55) < delta < timedelta(hours=2, seconds=5)


def test_rate_limit_backoff_capped_at_24h(db):
    """限流任务连续失败多次后，next_attempt 应封顶在 +24h，不再无限增长。
    设计动机：yfinance 是按 IP 限流，但有时 24h 后就降级；超 24h 等太久。
    同时不应永久 failed，否则需手动 reset 才能恢复。
    """
    rec = OverseasFinancialUpdate(
        ticker="NVDA", task="fy:2024", status="pending", error_count=0,
    )
    db.add(rec); db.flush()

    # 模拟 10 次连续 429
    before = datetime.utcnow()
    for _ in range(10):
        _record_result(db, rec, success=False, error="Too Many Requests")
    db.refresh(rec)

    # 即使失败 10 次（远超 MAX_RETRIES=5），状态仍 pending，不应永久 failed
    assert rec.status == "pending", "限流错误不应永久标记为 failed"
    # 退避封顶在 24h 而不是 6*10=60h
    delta = rec.next_attempt - before
    assert timedelta(hours=23, minutes=55) < delta < timedelta(hours=24, seconds=5), \
        f"应封顶 ~24h，实际 {delta}"
    assert rec.error_count == 10


def test_non_rate_limit_error_eventually_fails(db):
    """非限流错误（如网络超时）超过 MAX_RETRIES=5 次应永久 failed。
    限流错误才是永久重试，其他错误仍按旧规则失败。
    """
    rec = OverseasFinancialUpdate(
        ticker="AMD", task="fy:2024", status="pending", error_count=0,
    )
    db.add(rec); db.flush()

    for _ in range(6):  # > MAX_RETRIES
        _record_result(db, rec, success=False, error="ConnectionResetError: peer closed")
    db.refresh(rec)
    assert rec.status == "failed"
    assert rec.next_attempt is None


def test_reset_rate_limited_backoff_pushes_all_pending(db):
    """reset 工具应该把所有 error_count>0 的 pending 推到 t+6h。"""
    rec_a = OverseasFinancialUpdate(
        ticker="NVDA", task="fy:2024", status="pending",
        error_count=2, next_attempt=datetime.utcnow() + timedelta(minutes=10),
    )
    rec_b = OverseasFinancialUpdate(
        ticker="AMD", task="fy:2024", status="pending",
        error_count=1, next_attempt=datetime.utcnow() + timedelta(minutes=5),
    )
    rec_clean = OverseasFinancialUpdate(
        ticker="INTC", task="fy:2024", status="pending",
        error_count=0, next_attempt=None,
    )
    rec_success = OverseasFinancialUpdate(
        ticker="AVGO", task="fy:2024", status="success",
        error_count=0,
    )
    db.add_all([rec_a, rec_b, rec_clean, rec_success]); db.flush()
    n = reset_rate_limited_backoff(db)
    db.expire_all()
    assert n == 2
    # error_count>0 的两个都被推到 6h 后
    for rec in (rec_a, rec_b):
        db.refresh(rec)
        assert rec.next_attempt > datetime.utcnow() + timedelta(hours=5, minutes=30)
    # 干净的（error_count=0）pending 不动
    db.refresh(rec_clean)
    assert rec_clean.next_attempt is None
    # success 记录不碰
    db.refresh(rec_success)
    assert rec_success.next_attempt is None


def test_ensure_tasks_dedupes_tickers_across_companies(db):
    """GOOGL/INTC/SMSN 各对应多家公司时，ensure_tasks 只创建一份任务集合。

    之前的逻辑靠 exists 检查防重复 INSERT，仍然正确但会跑 12 次冗余 SELECT。
    新逻辑用 set 在外层就去重，节省查询次数。
    """
    # GOOGL = 3 家业务部门、INTC = 2 家、SMSN = 4 家
    googlers = ["Google", "Google Cloud", "Google Ads"]
    intlers = ["Intel", "Intel Foundry"]
    sams = ["Samsung Electronics", "Samsung Memory", "Samsung Foundry", "Samsung SDI"]
    for n in googlers:
        db.add(Company(name=n, ticker="GOOGL", company_type="internet", sector="AI"))
    for n in intlers:
        db.add(Company(name=n, ticker="INTC", company_type="chip_design", sector="CPU"))
    for n in sams:
        db.add(Company(name=n, ticker="SMSN", company_type="memory", sector="DRAM"))
    db.flush()

    created = ensure_tasks(db)
    assert created == 18  # 3 unique tickers × 6 tasks each

    # 每个 ticker 在表里恰好 6 条（不是 3×6=18 或 2×6=12 或 4×6=24）
    for t in ("GOOGL", "INTC", "SMSN"):
        n_rows = db.query(OverseasFinancialUpdate).filter_by(ticker=t).count()
        assert n_rows == 6, f"{t}: 期望 6 行，实际 {n_rows}"


def test_run_next_batch_skips_remaining_tickers_on_429(db, monkeypatch):
    """批内任一 ticker 撞 yfinance 429 后，剩余 ticker 不再触网，
    而是统一推迟到 6h 后再试（error_count 不增加，避免被滥用退避惩罚）。"""
    # 三个 ticker 各登记一家公司 + 各 6 个 pending 任务
    db.add_all([
        Company(name="NVIDIA", ticker="NVDA", company_type="chip_design", sector="GPU"),
        Company(name="AMD", ticker="AMD", company_type="chip_design", sector="GPU"),
        Company(name="AVGO", ticker="AVGO", company_type="chip_design", sector="semiconductor"),
    ])
    db.flush()

    for ticker in ("NVDA", "AMD", "AVGO"):
        for task in ("fy:2024", "fy:2025", "ttm:2026",
                      "pe:2024-12-31", "pe:2025-12-31", "pe:latest"):
            db.add(OverseasFinancialUpdate(ticker=ticker, task=task, status="pending"))
    db.commit()

    # 不管哪个 ticker 先被打到，都模拟 429（与 SQL 顺序无关）
    yf_calls: list[str] = []

    def fake_yf_obj(symbol: str):
        yf_calls.append(symbol)
        raise RuntimeError("Too Many Requests. Rate limited.")

    monkeypatch.setattr(ofc, "_yf_obj", fake_yf_obj)
    monkeypatch.setattr(ofc, "YFINANCE_DELAY_SECONDS", 0)
    monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)

    before = datetime.utcnow()
    stats = run_next_batch(db, tickers_per_run=3)

    # 整批只调用 1 次 yfinance（429 后整批放弃），剩下 2 个 ticker 跳过
    assert len(yf_calls) == 1, \
        f"整批应只调用 1 次 yfinance（429 后放弃），实际 {len(yf_calls)} 次: {yf_calls}"
    first_ticker = yf_calls[0]
    assert first_ticker in {"NVDA", "AMD", "AVGO"}

    # 第一个 ticker 的 6 个任务都被 429 标记
    first_recs = db.query(OverseasFinancialUpdate).filter_by(ticker=first_ticker).all()
    for rec in first_recs:
        assert rec.error_count == 1
        assert rec.status == "pending"
        assert "Too Many Requests" in (rec.last_error or "")

    # 剩余 2 个 ticker 的 pending 任务：error_count=0，next_attempt 推到 +6h
    other_tickers = {"NVDA", "AMD", "AVGO"} - {first_ticker}
    assert len(other_tickers) == 2
    for ticker in other_tickers:
        recs = db.query(OverseasFinancialUpdate).filter_by(ticker=ticker, status="pending").all()
        assert len(recs) == 6
        for rec in recs:
            assert rec.error_count == 0, f"{ticker} 不应被记错误（未触网）"
            assert rec.next_attempt is not None
            delta = rec.next_attempt - before
            assert timedelta(hours=5, minutes=55) < delta < timedelta(hours=6, seconds=5), \
                f"{ticker} 推迟窗口应≈6h，实际 {delta}"

    # 统计：第一个 ticker 算 processed + failed（硬失败计 1 次/ticker）；
    # 剩下 2 个算 rate_limited（未触网，单独计数）
    assert stats["processed"] == 1
    assert stats["failed"] == 1
    assert stats["rate_limited"] == 2


def test_defer_pending_tickers_no_error_count_increment(db):
    """_defer_pending_tickers 单纯推迟，不应增加 error_count。"""
    rec_a = OverseasFinancialUpdate(
        ticker="NVDA", task="fy:2024", status="pending",
        error_count=2, next_attempt=datetime.utcnow() + timedelta(minutes=5),
    )
    rec_b = OverseasFinancialUpdate(
        ticker="AMD", task="fy:2024", status="pending", error_count=0,
    )
    rec_skipped = OverseasFinancialUpdate(
        ticker="AVGO", task="fy:2024", status="success", error_count=0,
    )
    db.add_all([rec_a, rec_b, rec_skipped]); db.flush()
    before = datetime.utcnow()

    n = _defer_pending_tickers(db, ["NVDA", "AMD"], hours=6)

    assert n == 2
    db.expire_all()
    db.refresh(rec_a)
    db.refresh(rec_b)
    db.refresh(rec_skipped)

    # error_count 不被改（保持调度原因 vs 真实错误的差异）
    assert rec_a.error_count == 2
    assert rec_b.error_count == 0
    # pending 的 next_attempt 都推到 +6h
    for rec in (rec_a, rec_b):
        delta = rec.next_attempt - before
        assert timedelta(hours=5, minutes=55) < delta < timedelta(hours=6, seconds=5)
    # success 记录不碰
    assert rec_skipped.next_attempt is None
