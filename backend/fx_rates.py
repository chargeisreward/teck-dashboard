"""USD 交叉汇率工具：使用公开 CDN，优先命中缓存。"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

import requests
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import FxRateCache

logger = logging.getLogger(__name__)
FX_API_URL = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{tag}/v1/currencies/usd.json"


def fetch_usd_rates(for_date: Optional[date] = None) -> tuple[dict, date]:
    tag = "latest" if for_date is None else for_date.isoformat()
    url = FX_API_URL.format(tag=tag)
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    payload = resp.json()
    rates = {}
    for k, v in payload.get("usd", {}).items():
        if v is None:
            continue
        try:
            rates[k.upper()] = float(v)
        except (ValueError, TypeError):
            logger.debug(f"Skipping non-numeric FX rate {k}={v}")
    raw_date = payload.get("date")
    try:
        actual = datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else (for_date or date.today())
    except ValueError:
        actual = for_date or date.today()
    return rates, actual


def get_fx_rate(db: Session, base_currency: str, for_date: Optional[date] = None,
                max_lookback: int = 5) -> Optional[float]:
    base = base_currency.upper()
    if base == "USD":
        return 1.0

    target = for_date or date.today()
    if target > date.today():
        target = date.today()

    cached = db.query(FxRateCache).filter(
        FxRateCache.base_currency == base,
        FxRateCache.date == target,
    ).first()
    if cached:
        return cached.rate

    rate = None
    actual = target
    d = target
    for _ in range(max_lookback + 1):  # try target + up to max_lookback prior days
        try:
            rates, actual = fetch_usd_rates(d)
            rate = rates.get(base)
            if rate is not None:
                break
        except requests.RequestException as e:
            logger.warning(f"FX fetch failed for {base} {d}: {e}")
        d -= timedelta(days=1)

    if rate is None:
        logger.warning(f"No FX rate for {base} around {target}")
        return None

    row = FxRateCache(
        base_currency=base, quote_currency="USD", rate=rate,
        date=actual, source="fawazahmed0-cdn",
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        cached = db.query(FxRateCache).filter(
            FxRateCache.base_currency == base,
            FxRateCache.date == actual,
        ).first()
        if cached:
            return cached.rate
        raise
    return rate
