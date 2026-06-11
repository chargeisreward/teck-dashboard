"""
将 PriceCache 中的历史价格数据迁移到 MarketData 表，
修复"涨跌幅走势（90日）"图表为空的问题。
"""
import logging
from datetime import datetime
from database import SessionLocal
from models import PriceCache, MarketData, Company

logger = logging.getLogger(__name__)

def backfill_market_data():
    """从 PriceCache 读取历史价格，按 ticker→company 映射写入 MarketData"""
    db = SessionLocal()
    try:
        # 构建 ticker → company_id 映射
        companies = db.query(Company).filter(Company.ticker.isnot(None)).all()
        ticker_to_company = {}
        for c in companies:
            if c.ticker:
                key = c.ticker.upper().strip()
                if key not in ticker_to_company:
                    ticker_to_company[key] = []
                ticker_to_company[key].append(c.id)

        # 读取 PriceCache 中所有数据
        rows = db.query(PriceCache).order_by(PriceCache.ticker, PriceCache.date).all()
        logger.info(f"PriceCache total rows: {len(rows)}")

        inserted = 0
        skipped = 0
        for row in rows:
            ticker = row.ticker.upper().strip()
            company_ids = ticker_to_company.get(ticker)
            if not company_ids:
                skipped += 1
                continue

            for cid in company_ids:
                # 检查是否已存在
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
        logger.info(f"MarketData backfill: {inserted} rows inserted/updated, {skipped} rows skipped (no company match)")

        # 验证结果
        total = db.query(MarketData).count()
        companies_with_data = db.query(MarketData.company_id).distinct().count()
        logger.info(f"MarketData now has {total} rows for {companies_with_data} companies")
        return {"inserted": inserted, "skipped": skipped, "total": total}

    except Exception as e:
        db.rollback()
        logger.error(f"Backfill failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = backfill_market_data()
    print(f"Done: {result}")
