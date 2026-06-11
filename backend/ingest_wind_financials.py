"""
读取 Wind CLI 输出的 JSONL 数据，写入 Financial 表。
用法: bash wind_fetch_financials.sh | python ingest_wind_financials.py
"""
import json
import logging
import sys

from database import SessionLocal
from models import Company, Financial

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def parse_row(row: list, columns: list) -> dict | None:
    """解析 Wind 返回的单行数据"""
    try:
        rev_idx = next(i for i, c in enumerate(columns) if "营业收入" in c and "时间" not in c)
        net_idx = next(i for i, c in enumerate(columns) if "净利润" in c and "时间" not in c)
        pe_idx = next(i for i, c in enumerate(columns) if "市盈率" in c and "时间" not in c)
        time_idx = next(i for i, c in enumerate(columns) if "时间" in c)
    except StopIteration:
        return None

    time_str = row[time_idx] if time_idx < len(row) else ""
    if not time_str or "FY" not in str(time_str):
        return None

    try:
        fiscal_year = int(str(time_str).split("FY")[1])
    except (IndexError, ValueError):
        return None

    rev = row[rev_idx] if rev_idx < len(row) else None
    net = row[net_idx] if net_idx < len(row) else None
    pe = row[pe_idx] if pe_idx < len(row) else None

    return {
        "fiscal_year": fiscal_year,
        "revenue": round(float(rev) * 0.1, 2) if rev else None,  # 亿→B
        "net_income": round(float(net) * 0.1, 2) if net else None,  # 亿→B
        "pe": round(float(pe), 2) if pe else None,
        "pe_ttm": round(float(pe), 2) if pe else None,
    }


def process():
    db = SessionLocal()
    try:
        results = {"updated": 0, "skipped": 0, "errors": 0}

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 跳过元数据行
            if "total" in msg or "done" in msg:
                if "total" in msg:
                    logger.info(f"Processing {msg['total']} tickers...")
                continue

            ticker = msg.get("ticker")
            windcode = msg.get("windcode")
            if not msg.get("ok") or not msg.get("data"):
                logger.warning(f"[{ticker}] ({windcode}) Wind returned no data")
                results["skipped"] += 1
                continue

            try:
                content = msg["data"]["content"][0]["text"]
                payload = json.loads(content)
                rows = payload["data"]["data"]["rows"]
                columns = payload["data"]["data"]["columns"]
                col_names = [c["name"] for c in columns]
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                logger.warning(f"[{ticker}] Parse error: {e}")
                results["errors"] += 1
                continue

            # 找到所有匹配的 company_id
            companies = db.query(Company).filter(Company.ticker == ticker).all()
            if not companies:
                logger.warning(f"[{ticker}] No company found in DB")
                results["skipped"] += 1
                continue

            written = 0
            for row in rows:
                rec = parse_row(row, col_names)
                if not rec:
                    continue

                for co in companies:
                    existing = db.query(Financial).filter(
                        Financial.company_id == co.id,
                        Financial.fiscal_year == rec["fiscal_year"],
                    ).first()

                    if existing:
                        existing.revenue = rec["revenue"]
                        existing.net_income = rec["net_income"]
                        existing.pe = rec["pe"]
                        existing.pe_ttm = rec["pe_ttm"]
                    else:
                        db.add(Financial(
                            company_id=co.id,
                            fiscal_year=rec["fiscal_year"],
                            revenue=rec["revenue"],
                            net_income=rec["net_income"],
                            pe=rec["pe"],
                            pe_ttm=rec["pe_ttm"],
                        ))
                    written += 1

            db.commit()
            logger.info(f"[{ticker}] ({windcode}) ✅ {written} records ({[r['fiscal_year'] for r in [parse_row(r, col_names) for r in rows] if r]})")
            results["updated"] += 1

        logger.info(f"Done: {results}")
        return results

    finally:
        db.close()


if __name__ == "__main__":
    process()
