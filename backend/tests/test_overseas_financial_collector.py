from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch
import pandas as pd

from overseas_financial_collector import (
    update_financial,
    update_pe_snapshot,
    _record_result,
    reset_rate_limited_backoff,
)
from models import Financial, CompanyValuationSnapshot, Company, OverseasFinancialUpdate


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


def test_rate_limit_backoff_is_6_hours(db):
    """限流错误应该把 next_attempt 推到 t+6h（首次失败），不是 30 分钟。"""
    rec = OverseasFinancialUpdate(
        ticker="NVDA", task="fy:2024", status="pending",
        error_count=0,
    )
    db.add(rec); db.flush()
    before = datetime.utcnow()
    _record_result(db, rec, success=False, error="HTTPError: Too Many Requests")
    db.refresh(rec)
    assert rec.status == "pending"
    assert rec.error_count == 1
    delta = rec.next_attempt - before
    # 第一次限流：6h ± 5s 容差
    assert timedelta(hours=5, minutes=59, seconds=55) < delta < timedelta(hours=6, seconds=5)


def test_non_rate_limit_error_uses_exponential_backoff(db):
    """非限流的失败（如网络超时）仍然走指数退避 2h,4h,8h…"""
    rec = OverseasFinancialUpdate(
        ticker="AMD", task="fy:2024", status="pending",
        error_count=0,
    )
    db.add(rec); db.flush()
    before = datetime.utcnow()
    _record_result(db, rec, success=False, error="ConnectionResetError: peer closed")
    db.refresh(rec)
    assert rec.status == "pending"
    delta = rec.next_attempt - before
    assert timedelta(hours=1, seconds=55) < delta < timedelta(hours=2, seconds=5)


def test_reset_rate_limited_backoff_pushes_all_pending(db):
    """reset 工具应该把所有 error_count>0 的 pending 推到 t+6h。"""
    rec_a = OverseasFinancialUpdate(
        ticker="NVDA", task="fy:2024", status="pending",
        error_count=2, next_attempt=datetime.utcnow() + timedelta(minutes=10),
    )
    rec_b = OverseasFinancialUpdate(
        ticker="AMD", task="fy:2024", status="pending",
        error_count=1, next_attempt=datetime.utcnow() + timedelta(minutes=5),
    )
    rec_clean = OverseasFinancialUpdate(
        ticker="INTC", task="fy:2024", status="pending",
        error_count=0, next_attempt=None,
    )
    rec_success = OverseasFinancialUpdate(
        ticker="AVGO", task="fy:2024", status="success",
        error_count=0,
    )
    db.add_all([rec_a, rec_b, rec_clean, rec_success]); db.flush()
    n = reset_rate_limited_backoff(db)
    db.expire_all()
    assert n == 2
    # error_count>0 的两个都被推到 6h 后
    for rec in (rec_a, rec_b):
        db.refresh(rec)
        assert rec.next_attempt > datetime.utcnow() + timedelta(hours=5, minutes=30)
    # 干净的（error_count=0）pending 不动
    db.refresh(rec_clean)
    assert rec_clean.next_attempt is None
    # success 记录不碰
    db.refresh(rec_success)
    assert rec_success.next_attempt is None
