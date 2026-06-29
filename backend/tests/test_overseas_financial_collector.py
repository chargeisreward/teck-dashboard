from datetime import date
from unittest.mock import MagicMock, patch
import pandas as pd

from overseas_financial_collector import update_financial, update_pe_snapshot
from models import Financial, CompanyValuationSnapshot, Company


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
