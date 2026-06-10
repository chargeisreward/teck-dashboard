"""
公司数据校验与刷新模块

从腾讯财经 API + yfinance + akshare 拉取真实数据，更新本地数据库。
确保产业链全景页面使用真实市场数据而非种子数据。

数据源优先级:
  1. 腾讯财经 API (US/ADR/OTC 股票) — 实时报价 + PE_TTM + 市值
  2. yfinance (全球股票: 韩国 KOSPI, 日本等) — 财务数据 + 历史价格
  3. akshare (A 股) — 中国 A 股行情
"""
import logging
import time
from datetime import date, datetime

from price_data import (
    get_stock_info, _parse_tencent_quote, TENCENT_US_MAP,
    YFINANCE_TICKER_MAP, HAS_YFINANCE, HAS_AKSHARE,
    NAVER_KOREAN_MAP, _fetch_naver_korean_info,
)

logger = logging.getLogger(__name__)

# yfinance 限流保护：每次请求间隔(秒)
YFINANCE_DELAY = 3.0


def _get_yfinance_info(ticker: str) -> dict | None:
    """通过 yfinance 获取股票 info，带限流保护"""
    if not HAS_YFINANCE:
        return None
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info
        time.sleep(YFINANCE_DELAY)
        if info and info.get("marketCap"):
            return info
        return None
    except Exception as e:
        logger.warning(f"yfinance failed for {ticker}: {e}")
        return None


def _get_akshare_info(ticker: str) -> dict | None:
    """通过 akshare 获取 A 股实时行情"""
    if not HAS_AKSHARE:
        return None
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == ticker]
        if row.empty:
            return None
        row = row.iloc[0]
        return {
            "current_price": float(row.get("最新价", 0)),
            "change_pct": float(row.get("涨跌幅", 0)),
            "market_cap": float(row.get("总市值", 0)),
            "pe_ttm": float(row.get("市盈率-动态", 0)) if row.get("市盈率-动态") and row.get("市盈率-动态") != "-" else None,
            "name": row.get("名称", ""),
            "source": "akshare",
        }
    except Exception as e:
        logger.warning(f"akshare failed for {ticker}: {e}")
        return None


def _resolve_yfinance_ticker(ticker: str) -> str:
    """将内部 ticker 映射为 yfinance 可用的格式"""
    if ticker in YFINANCE_TICKER_MAP:
        return YFINANCE_TICKER_MAP[ticker]
    return ticker


def refresh_all_company_data(db) -> dict:
    """
    遍历所有链上公司，拉取真实数据并更新 DB。
    更新 financials 表和 stock_info_cache。

    数据获取策略:
      - US/ADR tickers in TENCENT_US_MAP → Tencent API (PE, price, mcap)
      - Korean tickers (000660, SMSN) → yfinance
      - Chinese A-stock (SMI) → akshare
      - All tickers → yfinance for revenue (with rate limiting)
    """
    from models import Company, CompanyChainLink, Financial, StockInfoCache

    # 获取所有链上公司（去重）
    chain_companies = (
        db.query(Company)
        .join(CompanyChainLink)
        .distinct()
        .all()
    )

    results = {"updated": 0, "skipped": 0, "errors": 0, "details": []}

    for co in chain_companies:
        ticker = co.ticker
        if not ticker:
            results["skipped"] += 1
            continue

        detail = {"company": co.name_cn or co.name, "ticker": ticker}

        try:
            cache_data = {}
            source = None

            # ── 1. 尝试从 Tencent API 获取实时数据 ──
            if ticker.upper() in TENCENT_US_MAP:
                live_data = _parse_tencent_quote(ticker.upper())
                if live_data:
                    source = "tencent"
                    detail["price_source"] = "tencent"
                    cache_data.update(live_data)

            # ── 2. Korean stocks via Naver API + yfinance fallback ──
            if ticker in NAVER_KOREAN_MAP:
                kr_data = _fetch_naver_korean_info(ticker)
                if kr_data:
                    source = "naver"
                    detail["price_source"] = "naver_kr"
                    cache_data.update({
                        "current_price": kr_data.get("current_price"),
                        "current_price_usd": kr_data.get("current_price_usd"),
                        "pe_ttm": kr_data.get("pe_ttm"),
                        "eps": kr_data.get("eps"),
                        "market_cap": kr_data.get("market_cap"),
                        "market_cap_b": kr_data.get("market_cap_b"),
                        "market_cap_krw": kr_data.get("market_cap_krw"),
                        "change_pct": kr_data.get("change_pct"),
                        "currency": "KRW",
                        "name": f"KR:{kr_data.get('kr_code','')}",
                    })
                elif HAS_YFINANCE:
                    # Fallback to yfinance
                    yf_ticker = _resolve_yfinance_ticker(ticker)
                    info = _get_yfinance_info(yf_ticker)
                    if info:
                        source = "yfinance"
                        detail["price_source"] = "yfinance_kr"
                        price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
                        pe = info.get("trailingPE") or info.get("forwardPE")
                        mcap = info.get("marketCap")
                        cache_data.update({
                            "current_price": float(price) if price else None,
                            "pe_ttm": float(pe) if pe else None,
                            "market_cap": float(mcap) if mcap else None,
                            "market_cap_b": round(float(mcap) / 1e8, 2) if mcap else None,
                            "name": info.get("shortName") or info.get("longName"),
                        })

            # ── 3. Chinese A-stock via akshare ──
            if ticker == "SMI" and HAS_AKSHARE:
                a_data = _get_akshare_info("688981")
                if a_data:
                    source = "akshare"
                    detail["price_source"] = "akshare"
                    cache_data.update(a_data)

            # ── 4. 从 yfinance 获取财务数据（营收等）──
            # 先尝试从 existing cache 获取已有数据，再补充 revenue
            existing_cache = db.query(StockInfoCache).filter(
                StockInfoCache.ticker == ticker.upper()
            ).first()
            existing_data = existing_cache.data_json if existing_cache and existing_cache.data_json else {}

            # 如果上一步已经用过 yfinance（如 Korean stocks），跳过重复调用
            if source not in ("yfinance",) and HAS_YFINANCE:
                # 尝试 yfinance 获取 revenue
                yf_ticker = _resolve_yfinance_ticker(ticker)
                info = _get_yfinance_info(yf_ticker)
                if info:
                    detail["yfinance"] = "ok"
                    rev = info.get("totalRevenue")
                    net_inc = info.get("netIncomeToCommon")
                    current_pe = cache_data.get("pe_ttm")
                    yf_pe = info.get("trailingPE")
                    cache_data.update({
                        "revenue": rev,
                        "revenue_b": round(float(rev) / 1e8, 2) if rev else existing_data.get("revenue_b"),
                        "net_income": net_inc,
                        "net_income_b": round(float(net_inc) / 1e8, 2) if net_inc else existing_data.get("net_income_b"),
                        "pe_ttm": float(current_pe) if current_pe else (float(yf_pe) if yf_pe else existing_data.get("pe_ttm")),
                        "ps_ttm": info.get("priceToSalesTrailing12Months"),
                        "pb": info.get("priceToBook"),
                        "dividend_yield": info.get("dividendYield"),
                        "sector": info.get("sector"),
                        "industry": info.get("industry"),
                        "long_name": info.get("longName"),
                        "short_name": info.get("shortName"),
                    })
                    if not source:
                        source = "yfinance"
                else:
                    detail["yfinance"] = "rate_limited"

            # ── 保留已有的 revenue 数据（如果本次没拉到）──
            if cache_data.get("revenue_b") is None and existing_data.get("revenue_b"):
                cache_data["revenue_b"] = existing_data["revenue_b"]
                cache_data["revenue"] = existing_data.get("revenue")

            cache_data["source"] = source

            if not cache_data and not existing_data:
                results["skipped"] += 1
                detail["status"] = "no_data"
                results["details"].append(detail)
                continue

            # ── 5. 写 StockInfoCache ──
            if existing_cache:
                merged = dict(existing_data)
                merged.update(cache_data)
                merged["source"] = source or merged.get("source")
                existing_cache.data_json = merged
                existing_cache.updated_at = date.today()
            else:
                db.add(StockInfoCache(
                    ticker=ticker.upper(),
                    data_json=cache_data,
                    updated_at=date.today(),
                ))

            # ── 6. 更新 Financials 表 ──
            pe_ttm_value = cache_data.get("pe_ttm")
            revenue_value = cache_data.get("revenue_b")
            mcap_value = cache_data.get("market_cap_b")

            if pe_ttm_value or revenue_value:
                fin = db.query(Financial).filter(
                    Financial.company_id == co.id,
                    Financial.fiscal_year == 2025,
                ).first()
                if fin:
                    if pe_ttm_value is not None:
                        fin.pe_ttm = float(pe_ttm_value)
                        fin.pe = float(pe_ttm_value)
                    if revenue_value is not None:
                        fin.revenue = float(revenue_value)
                else:
                    db.add(Financial(
                        company_id=co.id,
                        fiscal_year=2025,
                        revenue=float(revenue_value) if revenue_value else None,
                        pe_ttm=float(pe_ttm_value) if pe_ttm_value else None,
                        pe=float(pe_ttm_value) if pe_ttm_value else None,
                    ))

            db.commit()
            results["updated"] += 1
            detail["status"] = "ok"
            detail["pe_ttm"] = pe_ttm_value
            detail["revenue_b"] = revenue_value
            detail["source"] = source

        except Exception as e:
            db.rollback()
            logger.error(f"Refresh failed for {ticker}: {e}")
            results["errors"] += 1
            detail["status"] = "error"
            detail["error"] = str(e)[:100]

        results["details"].append(detail)

    return results


def verify_data_integrity(db) -> dict:
    """
    校验 Financial 表中数据是否为真实值。
    对比 stock_info_cache 和 financials 表。
    """
    from models import Company, CompanyChainLink, Financial, StockInfoCache

    issues = []
    chain_companies = (
        db.query(Company)
        .join(CompanyChainLink)
        .distinct()
        .all()
    )

    for co in chain_companies:
        ticker = co.ticker
        if not ticker:
            continue

        fin = db.query(Financial).filter(
            Financial.company_id == co.id,
            Financial.fiscal_year == 2025,
        ).first()

        cache = db.query(StockInfoCache).filter(
            StockInfoCache.ticker == ticker.upper()
        ).first()

        fin_pe = fin.pe_ttm if fin else None
        cache_pe = cache.data_json.get("pe_ttm") if cache and cache.data_json else None

        if fin_pe is not None and cache_pe is not None:
            diff = abs(float(fin_pe) - float(cache_pe))
            if diff > 5:
                issues.append({
                    "company": co.name_cn or co.name,
                    "ticker": ticker,
                    "fin_pe": fin_pe,
                    "cache_pe": cache_pe,
                    "diff": round(diff, 1),
                })

        # Check revenue
        fin_rev = fin.revenue if fin else None
        cache_rev = cache.data_json.get("revenue_b") if cache and cache.data_json else None
        if fin_rev is not None and cache_rev is not None:
            rev_diff = abs(float(fin_rev) - float(cache_rev))
            if rev_diff > 10:
                issues.append({
                    "company": co.name_cn or co.name,
                    "ticker": ticker,
                    "type": "revenue",
                    "fin_rev": fin_rev,
                    "cache_rev": cache_rev,
                    "diff": round(rev_diff, 1),
                })

    return {
        "total_companies": len(chain_companies),
        "issues_count": len(issues),
        "issues": issues,
    }
