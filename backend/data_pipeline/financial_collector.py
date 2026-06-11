"""Financial data collector — fetches company financials via wind-mcp-skill CLI."""
import json
import subprocess
import sys
from pathlib import Path
from datetime import date
from sqlalchemy.orm import Session

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from database import SessionLocal
from models import Company, Financial

WIND_SKILL_DIR = Path.home() / ".agents" / "skills" / "wind-mcp-skill"

# Map company types to Wind query indicators
QUERY_TEMPLATES = {
    "default": "{wind_code}2025revenuenet_incomesgross_marginnet_marginPEPBROEoperating_margin",
}

# Ticker to Wind code mapping
def to_wind_code(ticker: str, company_name: str) -> str:
    """Map known tickers to Wind codes."""
    mapping = {
        # US stocks: .O suffix
        "NVDA": "NVDA.O", "AMD": "AMD.O", "INTC": "INTC.O",
        "AVGO": "AVGO.O", "QCOM": "QCOM.O", "AAPL": "AAPL.O",
        "GOOGL": "GOOGL.O",
        "TSM": "TSM.O", "UMC": "UMC.O", "GFS": "GFS.O",
        "MU": "MU.O", "WDC": "WDC.O",
        "ASML": "ASML.O", "AMAT": "AMAT.O", "LRCX": "LRCX.O",
        "KLAC": "KLAC.O", "SNPS": "SNPS.O", "CDNS": "CDNS.O",
        "ARM": "ARM.O", "ANSS": "ANSS.O",
        "AMZN": "AMZN.O", "MSFT": "MSFT.O", "ORCL": "ORCL.O",
        "META": "META.O", "TSLA": "TSLA.O",
        "MRVL": "MRVL.O", "ANET": "ANET.O", "CSCO": "CSCO.O",
        "BIDU": "BIDU.O", "BABA": "BABA.O", "PDD": "PDD.O",
        # US OTC
        "TOELY": "TOELY.O", "ASMIY": "ASMIY.O", "ATEYY": "ATEYY.O",
        "SIEGY": "SIEGY.O", "MPNGY": "MPNGY.O",
        "TCEHY": "TCEHY.O", "XIACF": "XIACF.O",
        # Korean
        "000660": "000660.KS",
        # Taiwan (not TSM)
        "ASX": "ASX.O",  # ASE is US ADR
        "AMKR": "AMKR.O",  # Amkor US
        "SMI": "SMI.O",  # SMIC US ADR
    }
    return mapping.get(ticker, ticker)


def call_wind_api(question: str) -> dict:
    """Call wind-mcp-skill CLI and return parsed JSON result."""
    cmd = [
        "node", "scripts/cli.mjs", "call",
        "global_stock_data", "get_global_stock_fundamentals",
        json.dumps({"question": question}, ensure_ascii=False),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=False, cwd=str(WIND_SKILL_DIR), timeout=30
    )
    # Try UTF-8 first, then GBK fallback
    stdout = result.stdout
    if isinstance(stdout, bytes):
        try:
            stdout = stdout.decode("utf-8")
        except UnicodeDecodeError:
            stdout = stdout.decode("gbk", errors="replace")

    if result.returncode != 0:
        raise RuntimeError(f"Wind API error: {stdout[:500]}")
    data = json.loads(stdout)
    if data.get("isError") or not data.get("content"):
        raise RuntimeError(f"Wind API returned error: {data.get('error', 'unknown')}")
    # Parse the inner content text as JSON
    inner = json.loads(data["content"][0]["text"])
    return inner


def parse_financial_result(result: dict) -> dict:
    """Parse Wind API result into standardized financial dict."""
    data = result.get("data", {}).get("data", [])
    if not data:
        return {}

    columns = data[0].get("columns", [])
    rows = data[0].get("rows", [])
    if not rows:
        return {}

    row = rows[0]

    # Build column name -> index mapping
    col_map = {}
    for i, c in enumerate(columns):
        col_map[c["name"]] = i

    parsed = {}

    # Map Wind columns to our fields (values are in original currency units)
    field_mapping = {
        "2025年总营业收入": "revenue",
        "2025年营业收入": "revenue",       # fallback
        "2025年净利润": "net_income",
        "2025年销售毛利率": "gross_margin",
        "2025年销售净利率": "net_margin",
        "2025年营业利润率": "operating_margin",
        "2025年市盈率PE": "pe",
        "2025年市净率PB": "pb",
        "2025年净资产收益率ROE": "roe",
        "2025年每股收益EPS": "eps",
    }

    currency = row[-1] if len(row) > len(columns) else "USD"
    parsed["currency"] = currency

    for wind_name, our_name in field_mapping.items():
        if wind_name in col_map:
            val = row[col_map[wind_name]]
            if val is not None and val != "" and val != "—":
                try:
                    parsed[our_name] = float(val)
                except (ValueError, TypeError):
                    pass

    return parsed


def collect_all_financials(db: Session):
    """Fetch financial data for all companies from Wind and store in DB."""
    companies = db.query(Company).filter(Company.ticker.isnot(None)).all()

    today = date.today()
    stats = {"success": 0, "skipped": 0, "error": 0}

    for company in companies:
        ticker = company.ticker
        if not ticker:
            stats["skipped"] += 1
            continue

        # Check if we already have Wind data for this company (skip if fresh enough)
        existing = db.query(Financial).filter(
            Financial.company_id == company.id,
            Financial.data_source == "wind_api",
            Financial.fiscal_year == 2025,
        ).first()
        if existing and existing.last_verified and (today - existing.last_verified).days < 1:
            stats["skipped"] += 1
            continue

        wind_code = to_wind_code(ticker, company.name)
        question = f"{wind_code}2025revenuenetincomesgrossmarginnetmarginPEPBROEoperatingmargin"

        try:
            result = call_wind_api(question)
            parsed = parse_financial_result(result)

            if not parsed:
                print(f"  WARN {company.name} ({ticker}): no data returned")
                stats["error"] += 1
                continue

            # Create or update Financial record
            fin = existing or Financial(company_id=company.id)
            fin.fiscal_year = 2025
            fin.data_source = "wind_api"
            fin.last_verified = today

            if "revenue" in parsed:
                # Wind returns in 亿 (100M) of local currency.
                # Convert to 亿美元 (hundred million USD)
                rev_val = parsed["revenue"]
                currency = parsed.get("currency", "USD")
                if currency == "TWD":
                    rev_val = rev_val / 32.5       # TWD to USD
                elif currency == "JPY":
                    rev_val = rev_val / 150.0       # JPY to USD
                elif currency == "KRW":
                    rev_val = rev_val / 1350.0      # KRW to USD
                fin.revenue = round(rev_val, 2)

            if "net_income" in parsed:
                ni_val = parsed["net_income"]
                currency = parsed.get("currency", "USD")
                if currency == "TWD":
                    ni_val = ni_val / 32.5
                elif currency == "JPY":
                    ni_val = ni_val / 150.0
                elif currency == "KRW":
                    ni_val = ni_val / 1350.0
                fin.net_income = round(ni_val, 2)

            if "gross_margin" in parsed:
                fin.gross_margin = round(parsed["gross_margin"], 2)
            if "operating_margin" in parsed:
                fin.operating_margin = round(parsed["operating_margin"], 2)
            if "net_margin" in parsed:
                fin.net_margin = round(parsed["net_margin"], 2)
            if "pe" in parsed:
                fin.pe = round(parsed["pe"], 2)
            if "pb" in parsed:
                fin.pb = round(parsed["pb"], 2)
            if "roe" in parsed:
                fin.roe = round(parsed["roe"], 2)

            if not existing:
                db.add(fin)

            db.flush()
            print(f"  OK {company.name} ({ticker}): rev={fin.revenue}, PE={fin.pe}, GM={fin.gross_margin}%")
            stats["success"] += 1

        except Exception as e:
            print(f"  FAIL {company.name} ({ticker}): {str(e)[:100]}")
            stats["error"] += 1

    db.commit()
    return stats


def main():
    db = SessionLocal()
    try:
        print("Starting financial data collection from Wind API...")
        stats = collect_all_financials(db)
        print(f"\nDone: {stats['success']} success, {stats['skipped']} skipped, {stats['error']} errors")
    finally:
        db.close()


if __name__ == "__main__":
    main()
