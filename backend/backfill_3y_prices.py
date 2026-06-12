"""
补齐所有关注证券的过去3年复权价格数据。
使用已有数据源优先级: Tencent → yfinance → akshare。
yfinance 天然返回复权价格 (Adj Close)，腾讯 API 使用 qfq(前复权)。

数据流设计:
  - 首次启动: 调 backfill_3y_prices() 一次拉 3 年, 落地后不覆盖
  - 每日调度: 调 incremental_backfill_prices() 增量补缺口(只追加,不覆盖)
  - 设计动机: 数据 API 可能限流, 一次性 bulk 失败则需要靠调度逐步补足
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

# 历史数据窗口: 3 年 = 3 × 365 = 1095 天
# (略大于 3 calendar 年作为缓冲, 不含闰年)
HISTORY_DAYS = 3 * 365


def backfill_3y_prices(overwrite: bool = False):
    """为所有有 ticker 的公司补齐过去 3 年复权价格(append by default)

    overwrite=False (默认): 已存在数据不覆盖, 仅插入新日期
    overwrite=True: 重写全部数据(慎用)
    """
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

                # 拉取过去 3 年 (HISTORY_DAYS = 3 × 365 = 1095) 的复权价格
                data = fetch_price_history(ticker, days=HISTORY_DAYS)

                if data:
                    _write_to_cache(db, ticker, data, data[0].get("source", "live"), overwrite=overwrite)
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


def incremental_backfill_prices():
    """每日增量补缺口: 为每个 ticker 拉取 price_cache 最新日期之后的数据。

    调度在 refresh_company_financials (7:00 / 19:00) 调用, 保护首次失败后
    缺口永远填不上, 同时不覆盖已有数据 (overwrite=False)。

    策略:
      - ticker 已有最新数据: 跳过 (today - latest_date < 1)
      - ticker 已有部分数据: 拉取 (latest_date, today] 这段追加
      - ticker 无数据: 回退到首次 bulk 拉 3 年
    """
    db = SessionLocal()
    try:
        companies = db.query(Company).filter(Company.ticker.isnot(None)).all()
        seen_tickers = set()
        results = {"appended": 0, "skipped_up_to_date": 0, "errors": 0, "details": []}

        today = datetime.now().date()

        for co in companies:
            ticker = co.ticker.upper().strip()
            if not ticker or ticker in seen_tickers:
                continue
            seen_tickers.add(ticker)

            detail = {"ticker": ticker, "company": co.name_cn or co.name}

            try:
                latest = db.query(PriceCache).filter(
                    PriceCache.ticker == ticker
                ).order_by(PriceCache.date.desc()).first()
                latest_date = latest.date if latest else None

                if latest_date is None:
                    # 无任何数据, 回退到首次 bulk
                    days_to_fetch = HISTORY_DAYS
                    detail["strategy"] = "first_time_bulk"
                else:
                    # 已有数据, 拉增量 (latest_date+1, today]
                    days_to_fetch = (today - latest_date).days + 1
                    detail["strategy"] = "incremental"
                    detail["latest_date"] = str(latest_date)

                if days_to_fetch <= 0:
                    # 已最新
                    results["skipped_up_to_date"] += 1
                    detail["status"] = "up_to_date"
                    results["details"].append(detail)
                    continue

                detail["days_to_fetch"] = days_to_fetch
                data = fetch_price_history(ticker, days=days_to_fetch)

                if data:
                    # 追加模式: 不覆盖已有
                    _write_to_cache(db, ticker, data, data[0].get("source", "live"), overwrite=False)
                    db.commit()
                    detail["rows"] = len(data)
                    detail["source"] = data[0].get("source")
                    results["appended"] += 1
                    logger.info(f"[{ticker}] ✅ incremental: {len(data)} rows from {data[0]['date']} to {data[-1]['date']}")
                else:
                    detail["rows"] = 0
                    detail["error"] = "no_data"
                    logger.warning(f"[{ticker}] ⚠️ incremental returned no data")

                # yfinance 限流
                if data and data[0].get("source") == "yfinance":
                    time.sleep(YFINANCE_DELAY)

            except Exception as e:
                db.rollback()
                detail["error"] = str(e)[:100]
                results["errors"] += 1
                logger.error(f"[{ticker}] ❌ {e}")

            results["details"].append(detail)

        logger.info(
            f"Incremental backfill: appended={results['appended']}, "
            f"up_to_date={results['skipped_up_to_date']}, errors={results['errors']}"
        )
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
