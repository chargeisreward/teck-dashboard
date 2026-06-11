"""Macroeconomic data collector — fetches US and global macro indicators.

Data sources:
  Layer 1: FRED API (US macro, 80K+ series) — needs FRED_API_KEY in .env
  Layer 2: tedata (Trading Economics, 200+ countries) — pip install tedata + Selenium

Usage:
  python -m data_pipeline.macro_collector         # Incremental update
  python -m data_pipeline.macro_collector --full   # Full refresh
"""

import json
import logging
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from database import SessionLocal
from models import KeyIndicator, IndicatorObservation

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("macro_collector")

# Load .env
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_BASE = "https://api.stlouisfed.org/fred"

# ── FRED indicator definitions ──────────────────────────────────────
# (series_id, name, name_cn, unit, category, tier, related_tickers)
FRED_INDICATORS: list[tuple[str, str, str, str, str, int, str]] = [
    # ── GDP & Output ──
    ("GDP", "Gross Domestic Product", "美国GDP", "B USD", "GDP", 1,
     "NVDA,AMD,AVGO,TSM,ASML,AMAT"),
    ("GDPC1", "Real GDP", "美国实际GDP", "B Chn USD", "GDP", 1, ""),
    ("INDPRO", "Industrial Production Index", "美国工业生产指数", "Index 2017=100",
     "Industrial Production", 1, "NVDA,TSM,ASML,AMAT"),
    ("TCU", "Capacity Utilization", "美国产能利用率", "%", "Industrial Production", 1,
     "TSM,UMC,GFS,SMI"),

    # ── Inflation ──
    ("CPIAUCSL", "Consumer Price Index (CPI)", "美国CPI", "Index 1982-84=100",
     "Inflation", 1, ""),
    ("CPILFESL", "Core CPI (ex Food & Energy)", "美国核心CPI", "Index 1982-84=100",
     "Inflation", 1, ""),
    ("PPIACO", "Producer Price Index", "美国PPI", "Index 1982=100", "Inflation", 2,
     "NVDA,AMD,INTC"),
    ("PCE", "Personal Consumption Exp.", "美国PCE物价指数", "B USD", "Inflation", 1, ""),
    ("PCEPILFE", "Core PCE", "美国核心PCE", "B USD", "Inflation", 1, ""),

    # ── Employment ──
    ("PAYEMS", "Nonfarm Payrolls", "美国非农就业", "Thousands", "Employment", 1, ""),
    ("UNRATE", "Unemployment Rate", "美国失业率", "%", "Employment", 1, ""),
    ("AHEMAN", "Avg Hourly Earnings", "美国平均时薪", "USD/hr", "Employment", 2, ""),

    # ── Monetary & Rates ──
    ("FEDFUNDS", "Federal Funds Rate", "美国联邦基金利率", "%", "Monetary Policy", 1, ""),
    ("M2SL", "M2 Money Supply", "美国M2货币供应量", "B USD", "Monetary Policy", 1, ""),
    ("T10YIE", "10yr Breakeven Inflation", "美国10年期盈亏平衡通胀率", "%",
     "Bond Market", 2, ""),
    ("DGS10", "10-Year Treasury Yield", "美国10年期国债收益率", "%", "Bond Market", 1,
     "MSFT,AAPL,AMZN,GOOGL"),
    ("DGS2", "2-Year Treasury Yield", "美国2年期国债收益率", "%", "Bond Market", 1, ""),

    # ── Trade & Durables ──
    ("DGORDER", "Durable Goods Orders", "美国耐用品订单", "M USD", "Trade", 2,
     "NVDA,AMAT,LRCX,KLAC"),
    ("BOPTOT", "Trade Balance", "美国贸易余额", "M USD", "Trade", 2, ""),

    # ── Housing ──
    ("HOUST", "Housing Starts", "美国新屋开工", "Thousands", "Housing", 3, ""),

    # ── Semiconductor / Tech specific ──
    ("IPG334413", "Semiconductor Mfg Industrial Production",
     "美国半导体制造产出", "Index 2017=100", "Semiconductor", 1,
     "TSM,INTC,GFS,UMC,SMI"),
    ("IPG33441", "Semiconductor & Other Electronic Component Mfg",
     "美国半导体/电子元件制造产出", "Index 2017=100", "Semiconductor", 1,
     "NVDA,AMD,AVGO,TXN,QCOM"),
    ("CES3000000001", "All Employees: Manufacturing", "美国制造业就业人数",
     "Thousands", "Employment", 2, ""),
]

# Indicator series that should NOT use observation data (computed/index series)
SKIP_OBSERVATIONS = set()


def call_fred_api(endpoint: str, params: dict) -> dict[str, Any]:
    """Call FRED REST API and return parsed JSON."""
    params["api_key"] = FRED_API_KEY
    params["file_type"] = "json"
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"{FRED_BASE}/{endpoint}?{qs}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")[:200]
        logger.error(f"  FRED HTTP {e.code} for {endpoint}: {body}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"  FRED error for {endpoint}: {e}")
        return {"error": str(e)}


def ensure_indicator(db, series_id: str, name: str, name_cn: str,
                     unit: str, category: str, tier: int,
                     related: str) -> KeyIndicator:
    """Find or create a KeyIndicator record."""
    ind = db.query(KeyIndicator).filter(KeyIndicator.name == name).first()
    if not ind:
        ind = KeyIndicator(
            name=name, name_cn=name_cn, unit=unit,
            source="fred_api",
            source_url=f"https://fred.stlouisfed.org/series/{series_id}",
            category=category, tier=tier,
            is_automated=True,
            update_frequency="varies",
            collection_method="FRED REST API, automatic daily",
            related_tickers=related,
        )
        db.add(ind)
        db.flush()
    return ind


def fetch_fred_series(series_id: str, observation_start: str | None = None) -> list[dict]:
    """Fetch FRED series observations.

    Returns list of {"date": str, "value": float} sorted by date.
    """
    params: dict[str, Any] = {
        "series_id": series_id,
        "sort_order": "asc",
    }
    if observation_start:
        params["observation_start"] = observation_start

    # First get the series info to find earliest date
    info = call_fred_api("series", {"series_id": series_id})
    if info.get("error"):
        return []

    # Get observations
    result = call_fred_api("series/observations", params)
    if result.get("error"):
        return []

    obs = result.get("observations", [])
    data = []
    for o in obs:
        if o.get("value") and o["value"] != ".":
            try:
                val = float(o["value"])
                data.append({"date": o["date"], "value": val})
            except (ValueError, TypeError):
                pass
    return data


def update_fred_macro(db):
    """Update all FRED macro indicators."""
    if not FRED_API_KEY:
        logger.warning("  FRED_API_KEY not set — skipping FRED macro data")
        return 0

    logger.info("\n=== FRED Macro Data Collection ===")
    updated = 0

    # Get latest existing observation date across all indicators to minimize data pull
    latest_obs = db.query(IndicatorObservation).order_by(
        IndicatorObservation.date.desc()).first()
    if latest_obs:
        start_date = (latest_obs.date - timedelta(days=7)).isoformat()
    else:
        start_date = "2020-01-01"

    for (series_id, name, name_cn, unit, category, tier, related) in FRED_INDICATORS:
        ind = ensure_indicator(db, series_id, name, name_cn, unit, category, tier, related)
        data = fetch_fred_series(series_id, start_date)
        if not data:
            logger.info(f"  {series_id:15s} {name_cn:20s} no data (skipped)")
            continue

        new_count = 0
        for point in data:
            exists = db.query(IndicatorObservation).filter(
                IndicatorObservation.indicator_id == ind.id,
                IndicatorObservation.date == point["date"],
            ).first()
            if not exists:
                db.add(IndicatorObservation(
                    indicator_id=ind.id,
                    date=datetime.strptime(point["date"], "%Y-%m-%d").date(),
                    value=point["value"],
                    note="FRED API auto-collected",
                    data_quality="official",
                ))
                new_count += 1

        if new_count > 0:
            db.flush()
            updated += new_count
            # Show latest value
            last = data[-1]
            logger.info(f"  {series_id:15s} {name_cn:20s} +{new_count:3d} new · latest={last['value']:.2f} ({last['date']})")
        else:
            logger.info(f"  {series_id:15s} {name_cn:20s} up-to-date ({len(data)} obs)")

    db.commit()
    logger.info(f"  Total: {updated} new observations")
    return updated


def collect_macro(db=None):
    """Main entry point — collect all macro data."""
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        total = 0
        total += update_fred_macro(db)
        # Future: add tedata integration
        # total += collect_tedata_global(db)

        logger.info(f"\n{'='*50}")
        logger.info(f"Macro collection complete: {total} new observations")
        return total
    finally:
        if own_db:
            db.close()


def print_status(db=None):
    """Print current macro data status."""
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        indicators = db.query(KeyIndicator).order_by(KeyIndicator.tier).all()
        logger.info(f"\n{'='*70}")
        logger.info(f"{'Indicator':30s} {'Tier':6s} {'Obs':>5s} {'Latest':>20s}")
        logger.info(f"{'='*70}")
        for ind in indicators:
            latest = db.query(IndicatorObservation).filter(
                IndicatorObservation.indicator_id == ind.id
            ).order_by(IndicatorObservation.date.desc()).first()
            obs_count = db.query(IndicatorObservation).filter(
                IndicatorObservation.indicator_id == ind.id
            ).count()
            latest_str = f"{latest.value:.2f} ({latest.date})" if latest else "-"
            logger.info(f"{ind.name_cn or ind.name:30s} T{ind.tier:1d} {obs_count:5d} {latest_str:>20s}")
    finally:
        if own_db:
            db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Macroeconomic data collector")
    parser.add_argument("--full", action="store_true", help="Full refresh")
    parser.add_argument("--status", action="store_true", help="Print data status")
    args = parser.parse_args()

    if args.status:
        print_status()
    else:
        if not FRED_API_KEY:
            logger.info("=== Macro Data Collector ===")
            logger.warning("FRED_API_KEY not set. Set it in .env or environment variable.")
            logger.info("Get a free key: https://fred.stlouisfed.org/docs/api/api_key.html")
            logger.info("")
        collect_macro()
        print_status()
