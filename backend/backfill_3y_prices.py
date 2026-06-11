"""
补齐所有关注证券的过去3年复权价格数据。
使用已有数据源优先级: Tencent → yfinance → akshare。
yfinance 天然返回复权价格 (Adj Close)，腾讯 API 使用 qfq(前复权)。
"""
import logging
import time
from datetime import datetime, timedelta
from database import SessionLocal
from models import Company, PriceCache, MarketData
from price_data import fetch_price_history, _write_to_cache

logger = logging.getLogger(__name__)

# 限流保护
YFINANCE_DELAY = 2.0  # yfinance 调用间隔


def backfill_3y_prices():
    """为所有有 ticker 的公司补齐过去3年复权价格"""
    db = SessionLocal()
    try:
        companies = db.query(Company).filter(Company.ticker.isnot(None)).all()
        logger.info(f"Total companies with tickers: {len(companies)}")

        # 去重 ticker（同一 ticker 可能对应多家公司实体）
        seen_tickers = set()
        results = {"updated": 0, "skipped": 0, "errors": 0, "details": []}

        for co in companies:
            ticker = co.ticker.upper().strip()
            if not ticker or ticker in seen_tickers:
                continue
            seen_tickers.add(ticker)

            detail = {"ticker": ticker, "company": co.name_cn or co.name}

            try:
                # 已有数据量检查
                existing = db.query(PriceCache).filter(
                    PriceCache.ticker == ticker
                ).count()
                latest = db.query(PriceCache).filter(
                    PriceCache.ticker == ticker
                ).order_by(PriceCache.date.desc()).first()
                latest_date = latest.date if latest else None

                logger.info(f"[{ticker}] Fetching 3y price data (existing: {existing} rows, latest: {latest_date})")

                # 拉取过去 3 年 (1095天) 的复权价格
                data = fetch_price_history(ticker, days=1095)

                if data:
                    _write_to_cache(db, ticker, data, data[0].get("source", "live"))
                    db.commit()
                    detail["rows"] = len(data)
                    detail["source"] = data[0].get("source")
                    detail["date_range"] = f"{data[0]['date']} ~ {data[-1]['date']}"
                    results["updated"] += 1
                    logger.info(f"[{ticker}] ✅ {len(data)} rows from {data[0]['source']}: {data[0]['date']} ~ {data[-1]['date']}")
                else:
                    detail["rows"] = 0
                    detail["error"] = "no_data"
                    results["skipped"] += 1
                    logger.warning(f"[{ticker}] ⚠️ No data from any source")

                # yfinance 限流
                if data and data[0].get("source") == "yfinance":
                    time.sleep(YFINANCE_DELAY)

            except Exception as e:
                db.rollback()
                detail["error"] = str(e)[:100]
                results["errors"] += 1
                logger.error(f"[{ticker}] ❌ {e}")

            results["details"].append(detail)

        return results

    finally:
        db.close()


def sync_market_data():
    """将 PriceCache 最新数据同步到 MarketData 表"""
    db = SessionLocal()
    try:
        from models import Company
        companies = db.query(Company).filter(Company.ticker.isnot(None)).all()
        ticker_to_company = {}
        for c in companies:
            if c.ticker:
                key = c.ticker.upper().strip()
                ticker_to_company.setdefault(key, []).append(c.id)

        rows = db.query(PriceCache).order_by(PriceCache.date).all()
        inserted = 0
        for row in rows:
            ticker = row.ticker.upper().strip()
            company_ids = ticker_to_company.get(ticker)
            if not company_ids:
                continue
            for cid in company_ids:
                existing = db.query(MarketData).filter(
                    MarketData.company_id == cid,
                    MarketData.date == row.date,
                ).first()
                if existing:
                    existing.stock_price = row.price
                    existing.volume = row.volume
                else:
                    db.add(MarketData(
                        company_id=cid,
                        date=row.date,
                        stock_price=row.price,
                        volume=row.volume,
                    ))
                inserted += 1

        db.commit()
        total = db.query(MarketData).count()
        companies_with_data = db.query(MarketData.company_id).distinct().count()
        logger.info(f"MarketData synced: {inserted} ops, now {total} rows for {companies_with_data} companies")
        return {"inserted": inserted, "total": total, "companies": companies_with_data}

    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("=" * 60)
    print("Phase 1: Backfill 3-year adjusted prices → PriceCache")
    print("=" * 60)
    t0 = time.time()
    r1 = backfill_3y_prices()
    elapsed = time.time() - t0
    print(f"\nDone: {r1['updated']} updated, {r1['skipped']} skipped, {r1['errors']} errors ({elapsed:.0f}s)")

    print("\n" + "=" * 60)
    print("Phase 2: Sync PriceCache → MarketData")
    print("=" * 60)
    r2 = sync_market_data()
    print(f"Done: {r2['inserted']} ops, {r2['total']} total rows")
