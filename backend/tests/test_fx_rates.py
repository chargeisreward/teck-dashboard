from datetime import date
from unittest.mock import patch, MagicMock

from sqlalchemy.exc import IntegrityError

from fx_rates import get_fx_rate
from models import FxRateCache


def test_get_fx_rate_caches_and_returns_rate(db):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"date": "2025-12-31", "usd": {"krw": 1370.5}}
    mock_resp.raise_for_status = MagicMock()

    with patch("fx_rates.requests.get", return_value=mock_resp):
        rate = get_fx_rate(db, "KRW", date(2025, 12, 31))

    assert rate == 1370.5
    cached = db.query(FxRateCache).filter_by(base_currency="KRW", date=date(2025, 12, 31)).first()
    assert cached is not None
    assert cached.rate == 1370.5


def test_usd_returns_one_without_network(db):
    with patch("fx_rates.requests.get") as mock_get:
        rate = get_fx_rate(db, "USD", date(2025, 12, 31))
    assert rate == 1.0
    mock_get.assert_not_called()


def test_cache_hit_skips_network(db):
    db.add(FxRateCache(
        base_currency="EUR", quote_currency="USD", rate=0.92,
        date=date(2025, 12, 31), source="fawazahmed0-cdn",
    ))
    db.commit()

    with patch("fx_rates.requests.get") as mock_get:
        rate = get_fx_rate(db, "EUR", date(2025, 12, 31))
    assert rate == 0.92
    mock_get.assert_not_called()


def test_duplicate_cache_write_is_idempotent(db):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"date": "2025-12-31", "usd": {"krw": 1370.5}}
    mock_resp.raise_for_status = MagicMock()

    with patch("fx_rates.requests.get", return_value=mock_resp):
        rate1 = get_fx_rate(db, "KRW", date(2025, 12, 31))
        rate2 = get_fx_rate(db, "KRW", date(2025, 12, 31))

    assert rate1 == rate2 == 1370.5
