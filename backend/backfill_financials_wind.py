"""
通过 Wind 补齐所有证券过去 3 年（FY2023-FY2025）财务数据。
Wind 次数有限，务必高效使用。

数据映射：
  Wind 营业收入(亿元) → Financial.revenue (单位: B = billions, 1亿 = 0.1B)
  Wind 净利润(亿元)   → Financial.net_income (单位: B)
  Wind 市盈率PE       → Financial.pe_ttm / Financial.pe
"""
import json
import logging
import os
import subprocess
import sys
import shutil
from datetime import datetime

from database import SessionLocal
from models import Company, Financial

logger = logging.getLogger(__name__)

# Wind 代码后缀映射
WIND_SUFFIX = {
    "US": ".O",     # NASDAQ 默认 .O
    "NYSE": ".N",   # NYSE .N
    "HK": ".HK",    # 港股
    "SH": ".SH",    # A 股上海
    "SZ": ".SZ",    # A 股深圳
}

# 需要指定交易所的 ticker（默认 .O，特殊处理）
NYSE_TICKERS = {"ASML", "TSM", "UMC", "AMX"}

# Wind MCP skill 路径
WIND_SKILL_DIR = os.path.expanduser("~/.claude/skills/wind-mcp-skill")


def ticker_to_windcode(ticker: str) -> str | None:
    """将内部 ticker 转换为 Wind 代码"""
    t = ticker.upper().strip()

    # 港股 (HK tickers from akshare)
    if t in ("BIDU", "TCEHY", "BABA", "XIACF", "MPNGY"):
        hk_map = {"BIDU": "09888.HK", "TCEHY": "00700.HK", "BABA": "09988.HK",
                  "XIACF": "01810.HK", "MPNGY": "03690.HK"}
        return hk_map[t]

    # 韩国股票 - Wind 可能不支持直接查询，跳过
    if t in ("000660", "SMSN"):
        return None

    # A 股
    if t == "SMI":
        return "688981.SH"

    # 美股
    suffix = ".N" if t in NYSE_TICKERS else ".O"
    return f"{t}{suffix}"


WIND_CLI = os.path.join(
    os.path.expanduser("~/.claude/skills/wind-mcp-skill"),
    "scripts", "cli.mjs"
)


def call_wind_fundamentals(windcode: str) -> dict | None:
    """调用 Wind MCP CLI 获取财务数据"""
    question = f"{windcode}202320242025annualrevenuenetincomepe"
    node_exe = shutil.which("node") or "node"
    try:
        result = subprocess.run(
            [node_exe, WIND_CLI, "call",
             "global_stock_data", "get_global_stock_fundamentals",
             json.dumps({"question": question}, ensure_ascii=False)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 or not result.stdout:
            logger.warning(f"Wind CLI error for {windcode}: rc={result.returncode}, stderr={result.stderr[:200]}")
            return None

        data = json.loads(result.stdout)
        if data.get("isError") or not data.get("content"):
            err = data.get("error", {})
            logger.warning(f"Wind API error for {windcode}: {err.get('code')}")
            return None

        text = data["content"][0]["text"]
        payload = json.loads(text)
        rows = payload.get("data", {}).get("data", {}).get("rows", [])
        if not rows:
            logger.warning(f"No rows for {windcode}")
            return None

        return {
            "rows": rows,
            "columns": payload["data"]["data"]["columns"],
        }
    except subprocess.TimeoutExpired:
        logger.warning(f"Wind timeout for {windcode}")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Wind JSON error for {windcode}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Wind failed for {windcode}: {e}")
        return None


def parse_financials(windcode: str, result: dict) -> list[dict]:
    """将 Wind 返回解析为 Financial 表记录"""
    records = []
    columns = [c["name"] for c in result["columns"]]

    # 找到 Wind 列索引
    idx_revenue = next(i for i, n in enumerate(columns) if "营业收入" in n)
    idx_net_income = next(i for i, n in enumerate(columns) if "净利润" in n)
    idx_pe = next(i for i, n in enumerate(columns) if "市盈率" in n)
    idx_time = next(i for i, n in enumerate(columns) if "营业收入" in n and "时间" in n)

    for row in result["rows"]:
        rev_yi = row[idx_revenue]  # 亿元
        net_yi = row[idx_net_income]  # 亿元
        pe = row[idx_pe]
        time_str = row[idx_time]  # e.g. "Q4 FY2025"

        if not time_str:
            continue

        # 解析 fiscal_year
        try:
            fiscal_year = int(time_str.split("FY")[1])
        except (IndexError, ValueError):
            continue

        records.append({
            "fiscal_year": fiscal_year,
            "revenue": round(rev_yi * 0.1, 2) if rev_yi else None,  # 亿→B
            "net_income": round(net_yi * 0.1, 2) if net_yi else None,  # 亿→B
            "pe": round(pe, 2) if pe else None,
            "pe_ttm": round(pe, 2) if pe else None,
        })

    return records


def backfill_financials_wind():
    """主流程：遍历所有公司，用 Wind 补齐 3 年财务数据"""
    db = SessionLocal()
    try:
        companies = db.query(Company).filter(Company.ticker.isnot(None)).all()
        seen_tickers = set()
        results = {"updated": 0, "skipped": 0, "errors": 0, "details": []}

        for co in companies:
            ticker = co.ticker.upper().strip()
            if not ticker or ticker in seen_tickers:
                continue
            seen_tickers.add(ticker)

            windcode = ticker_to_windcode(ticker)
            if not windcode:
                logger.info(f"[{ticker}] No Wind mapping, skipping")
                results["skipped"] += 1
                continue

            detail = {"ticker": ticker, "windcode": windcode, "company": co.name_cn or co.name}

            try:
                logger.info(f"[{ticker}] → {windcode}: Fetching from Wind...")
                wind_result = call_wind_fundamentals(windcode)
                if not wind_result:
                    detail["status"] = "no_data"
                    results["skipped"] += 1
                    continue

                records = parse_financials(windcode, wind_result)
                if not records:
                    detail["status"] = "no_records"
                    results["skipped"] += 1
                    continue

                # 写入 Financial 表
                written = 0
                for rec in records:
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
                detail["fy"] = [r["fiscal_year"] for r in records]
                detail["status"] = "ok"
                results["updated"] += 1
                logger.info(f"[{ticker}] ✅ Written {written} years: {detail['fy']}")

            except Exception as e:
                db.rollback()
                detail["status"] = "error"
                detail["error"] = str(e)[:100]
                results["errors"] += 1
                logger.error(f"[{ticker}] ❌ {e}")

            results["details"].append(detail)

        return results

    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=" * 60)
    print("Backfill 3-year financials from Wind")
    print("=" * 60)
    r = backfill_financials_wind()
    print(f"\nResults: {r['updated']} updated, {r['skipped']} skipped, {r['errors']} errors")
