from datetime import date

from models import Company, CompanyValuationSnapshot
from valuation_snapshot_service import get_latest_pe_snapshot, get_latest_market_cap_snapshot


def test_get_latest_pe_snapshot(db):
    co = Company(name="TestCo", ticker="TST", company_type="chip_design", sector="x")
    db.add(co)
    db.flush()
    db.add(CompanyValuationSnapshot(
        company_id=co.id, snapshot_date=date(2025, 12, 31), pe_ttm=25.0
    ))
    db.add(CompanyValuationSnapshot(
        company_id=co.id, snapshot_date=date(2026, 6, 25), pe_ttm=22.0
    ))
    db.commit()
    snap = get_latest_pe_snapshot(db, co.id)
    assert snap.pe_ttm == 22.0


def test_get_latest_market_cap_snapshot(db):
    co = Company(name="TestCo2", ticker="TST2", company_type="chip_design", sector="x")
    db.add(co)
    db.flush()
    db.add(CompanyValuationSnapshot(
        company_id=co.id, snapshot_date=date(2026, 6, 25), market_cap_b=1500.0
    ))
    db.commit()
    snap = get_latest_market_cap_snapshot(db, co.id)
    assert snap.market_cap_b == 1500.0
