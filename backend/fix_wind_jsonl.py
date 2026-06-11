"""
修复 bash 生成的 Wind JSONL 文件，将多行 JSON 合并为单行后，写入 Financial 表。
读取 /tmp/wind_financials.jsonl，每行是一个不完整的 JSON，需要解析出 ticker 和 data 部分。
"""
import json
import logging
import os
import re

from database import SessionLocal
from models import Company, Financial

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Windows compat: bash /tmp/ maps to C:\Users\...\Temp, but Python sees D:\tmp\
INPUT = "/tmp/wind_financials.jsonl"
if not os.path.exists(INPUT):
    alt = os.path.join(os.environ.get("TEMP", "C:/tmp"), "wind_financials.jsonl")
    if os.path.exists(alt):
        INPUT = alt


def extract_json_from_line(line: str) -> dict | None:
    """从松散格式的行中提取 ticker, windcode, ok 和 data 字段"""
    ticker_m = re.search(r'"ticker":"(\w+)"', line)
    windcode_m = re.search(r'"windcode":"([\w.]+)"', line)
    ok_m = re.search(r'"ok":(true|false)', line)

    if not ticker_m or not windcode_m:
        return None

    result = {
        "ticker": ticker_m.group(1),
        "windcode": windcode_m.group(1),
        "ok": ok_m.group(1) == "true" if ok_m else False,
    }

    if result["ok"]:
        data_start = line.find('"data":{')
        if data_start >= 0:
            raw = line[data_start + 7:]  # starts with { of the data value
            try:
                decoder = json.JSONDecoder()
                data, _ = decoder.raw_decode(raw)
                result["data"] = data
            except json.JSONDecodeError:
                pass

    return result


def process():
    db = SessionLocal()
    try:
        # Build ticker → company_ids
        companies = db.query(Company).filter(Company.ticker.isnot(None)).all()
        ticker_to_ids = {}
        for c in companies:
            t = c.ticker.upper().strip()
            ticker_to_ids.setdefault(t, []).append(c.id)

        logger.info(f"Found {len(ticker_to_ids)} tickers in DB")

        with open(INPUT, "r", encoding="utf-8") as f:
            raw_lines = f.read()

        # Split by ticker pattern to handle multi-line entries
        entries = re.split(r'\n(?={"ticker":)', raw_lines)
        entries = [e.strip() for e in entries if e.strip()]
        logger.info(f"Found {len(entries)} entries in JSONL")

        updated = 0
        skipped = 0

        for entry in entries:
            info = extract_json_from_line(entry)
            if not info or not info["ok"]:
                skipped += 1
                continue

            ticker = info["ticker"]
            windcode = info["windcode"]
            data = info.get("data")

            if not data:
                skipped += 1
                continue

            try:
                content_text = data["content"][0]["text"]
                payload = json.loads(content_text)
                # Wind returns data.data as array
                inner = payload["data"]["data"][0]
                rows = inner["rows"]
                columns = inner["columns"]
                col_names = [c["name"] for c in columns]
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                logger.warning(f"[{ticker}] Parse error: {e}")
                skipped += 1
                continue

            # Find column indices
            try:
                rev_idx = next(i for i, n in enumerate(col_names) if "营业收入" in n and "时间" not in n)
                net_idx = next(i for i, n in enumerate(col_names) if "净利润" in n and "时间" not in n)
                pe_idx = next(i for i, n in enumerate(col_names) if "市盈率" in n and "时间" not in n)
                time_idx = next(i for i, n in enumerate(col_names) if "时间" in n)
            except StopIteration:
                skipped += 1
                continue

            company_ids = ticker_to_ids.get(ticker, [])
            if not company_ids:
                logger.warning(f"[{ticker}] No company match")
                skipped += 1
                continue

            written = 0
            for row in rows:
                time_str = row[time_idx] if time_idx < len(row) else ""
                if not time_str or "FY" not in str(time_str):
                    continue
                try:
                    fiscal_year = int(str(time_str).split("FY")[1])
                except (IndexError, ValueError):
                    continue

                rev = float(row[rev_idx]) * 0.1 if rev_idx < len(row) and row[rev_idx] is not None else None
                net = float(row[net_idx]) * 0.1 if net_idx < len(row) and row[net_idx] is not None else None
                pe = float(row[pe_idx]) if pe_idx < len(row) and row[pe_idx] is not None else None

                rev = round(rev, 2) if rev else None
                net = round(net, 2) if net else None
                pe = round(pe, 2) if pe else None

                for cid in company_ids:
                    existing = db.query(Financial).filter(
                        Financial.company_id == cid,
                        Financial.fiscal_year == fiscal_year,
                    ).first()
                    if existing:
                        existing.revenue = rev
                        existing.net_income = net
                        existing.pe = pe
                        existing.pe_ttm = pe
                    else:
                        db.add(Financial(
                            company_id=cid, fiscal_year=fiscal_year,
                            revenue=rev, net_income=net, pe=pe, pe_ttm=pe,
                        ))
                    written += 1

            db.commit()
            updated += 1
            logger.info(f"[{ticker}] {windcode}: {written} records")

        logger.info(f"\nDone: {updated} updated, {skipped} skipped")

    finally:
        db.close()


if __name__ == "__main__":
    process()
