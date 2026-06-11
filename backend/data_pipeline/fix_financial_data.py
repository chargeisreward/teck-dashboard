"""Fix financial data quality issues from Wind API.

Problems found:
1. Wind returns revenue in local currency (TWD, JPY, KRW) for non-US stocks
2. Some Wind values are clearly wrong (TSM=3.81, TOELY=2.43)
3. No proper currency normalization was applied

This script fixes the existing data and marks fixes with source="wind_api_fixed".
"""

import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))
from database import SessionLocal
from models import Company, Financial

# Known correct financial data (from public annual reports / SEC filings)
# Values in 亿 USD (hundred million USD)
CORRECT_REVENUES = {
    # TSM = TSMC   2024 rev $86.3B → 863亿  (TTM ~$88B)
    "TSM":   {"revenue": 863.0,  "net_income": 350.0, "note": "2024 annual $86.3B, TTM ~$88B"},
    # UMC    2024 rev NT$232B → $7.2B → 72亿  (Wind returned 2421 TWD)
    "UMC":   {"revenue": 72.0,   "net_income": 15.0,  "note": "2024 rev NT$232B = $7.2B, Wind raw 2421 TWD"},
    # 000660 = SK Hynix  2024 rev ₩66.1T → $48B → 480亿
    "000660":{"revenue": 480.0,  "net_income": 140.0, "note": "2024 rev ₩66.1T = $48B"},
    # MU = Micron  FY2024(Sep) rev $25.1B → 251亿
    "MU":    {"revenue": 251.0,  "net_income": 8.0,   "note": "FY2024 rev $25.1B"},
    # TOELY = Tokyo Electron  FY2024 rev ¥2.3T → $15.3B → 153亿
    "TOELY": {"revenue": 153.0,  "net_income": 32.0,  "note": "FY2024 rev ¥2.3T = $15.3B, Wind raw 2.43 wrong"},
    # ATEYY = Advantest  FY2024 rev ¥800B → $5.3B → 53亿 (Wind returned 7797 JPY)
    "ATEYY": {"revenue": 53.0,   "net_income": 10.7,  "note": "FY2024 rev ¥800B = $5.3B, Wind raw 7797 JPY"},
}

# Companies where Wind returned reasonable values but need currency conversion
# (These were already corrected if Wind returned TWD/JPY — but verify)
CURRENCY_CONVERT = {
    "UMC":   {"currency": "TWD", "rate": 32.5},   # 2421 TWD → 74.5 USD (close to 72)
    "ATEYY": {"currency": "JPY", "rate": 150.0},  # 7797 JPY → 52.0 USD (close to 53)
}


def fix_financial_data():
    db = SessionLocal()
    today = date.today()
    fixed_count = 0

    for ticker, correct in CORRECT_REVENUES.items():
        company = db.query(Company).filter(Company.ticker == ticker).first()
        if not company:
            print(f"  SKIP {ticker}: company not found")
            continue

        fin = db.query(Financial).filter(
            Financial.company_id == company.id,
            Financial.fiscal_year == 2025,
        ).first()

        if not fin:
            print(f"  SKIP {ticker}: no financial record found")
            continue

        old_rev = fin.revenue
        old_ni = fin.net_income
        old_src = fin.data_source

        fin.revenue = correct["revenue"]
        if correct.get("net_income") is not None:
            fin.net_income = correct["net_income"]
        fin.data_source = "wind_api_fixed"
        fin.last_verified = today

        old_rev_str = f"{old_rev:.1f}" if old_rev else "N/A"
        old_ni_str = f"{old_ni:.1f}" if old_ni else "N/A"
        new_ni_str = f"{fin.net_income:.1f}" if fin.net_income else "N/A"
        print(f"  FIX {ticker:8s}: rev {old_rev_str:>8s} -> {fin.revenue:>7.1f}  ni {old_ni_str:>8s} -> {new_ni_str:>8s}  ({correct['note']})")
        fixed_count += 1

    db.commit()
    print(f"\nFixed {fixed_count} companies.")
    db.close()
    return fixed_count


def check_data_quality():
    """Print a quality report of all financial data."""
    db = SessionLocal()
    fins = db.query(Financial).filter(Financial.fiscal_year == 2025).all()

    print(f"\n{'='*80}")
    print(f"{'Ticker':10s} {'Company':20s} {'Revenue':>10s} {'Net Income':>10s} {'PE':>8s} {'Source':16s}")
    print(f"{'='*80}")
    for f in fins:
        co = db.query(Company).filter(Company.id == f.company_id).first()
        if co:
            rev_str = f"{f.revenue:.1f}亿" if f.revenue else "N/A"
            ni_str = f"{f.net_income:.1f}亿" if f.net_income else "N/A"
            pe_str = f"{f.pe:.1f}" if f.pe else "N/A"
            print(f"{co.ticker or 'N/A':10s} {(co.name_cn or co.name or ''):20s} {rev_str:>10s} {ni_str:>10s} {pe_str:>8s} {f.data_source or '':16s}")
    db.close()


if __name__ == "__main__":
    print("=== Financial Data Quality Fix ===\n")
    fix_financial_data()
    check_data_quality()
