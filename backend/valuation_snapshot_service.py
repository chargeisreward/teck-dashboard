"""读取 CompanyValuationSnapshot 的辅助函数。"""
from datetime import date

from sqlalchemy.orm import Session

from models import CompanyValuationSnapshot


def get_latest_pe_snapshot(db: Session, company_id: int) -> CompanyValuationSnapshot | None:
    return (
        db.query(CompanyValuationSnapshot)
        .filter(CompanyValuationSnapshot.company_id == company_id)
        .order_by(CompanyValuationSnapshot.snapshot_date.desc())
        .first()
    )


def get_pe_snapshot_for_date(db: Session, company_id: int, snapshot_date) -> CompanyValuationSnapshot | None:
    d = snapshot_date if isinstance(snapshot_date, date) else date.fromisoformat(snapshot_date)
    return (
        db.query(CompanyValuationSnapshot)
        .filter(
            CompanyValuationSnapshot.company_id == company_id,
            CompanyValuationSnapshot.snapshot_date == d,
        )
        .first()
    )


def get_latest_market_cap_snapshot(db: Session, company_id: int) -> CompanyValuationSnapshot | None:
    return (
        db.query(CompanyValuationSnapshot)
        .filter(
            CompanyValuationSnapshot.company_id == company_id,
            CompanyValuationSnapshot.market_cap_b.isnot(None),
        )
        .order_by(CompanyValuationSnapshot.snapshot_date.desc())
        .first()
    )
