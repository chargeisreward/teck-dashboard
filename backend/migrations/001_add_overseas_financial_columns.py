"""Add overseas financial columns and new tables."""
import logging
import sys
from pathlib import Path

# This script lives in backend/migrations/. Add backend/ to sys.path so we can import database/models.
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

try:
    from sqlalchemy import text
    from database import engine
    from models import FxRateCache, OverseasFinancialUpdate, CompanyValuationSnapshot
except ImportError as e:
    raise RuntimeError(
        f"Cannot import backend modules. Please run this script from the repo root or backend/ directory. ({e})"
    ) from e

logger = logging.getLogger(__name__)

NEW_FINANCIAL_COLUMNS = [
    ("currency", "VARCHAR"),
    ("fx_rate", "FLOAT"),
    ("original_revenue", "FLOAT"),
    ("original_net_income", "FLOAT"),
]

NEW_TABLES = [FxRateCache, OverseasFinancialUpdate, CompanyValuationSnapshot]


def migrate():
    for table_cls in NEW_TABLES:
        table_cls.__table__.create(bind=engine, checkfirst=True)

    with engine.connect() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(financials)"))}
        for col, dtype in NEW_FINANCIAL_COLUMNS:
            if col not in existing:
                # col/dtype are hardcoded internal constants, safe for f-string
                conn.execute(text(f"ALTER TABLE financials ADD COLUMN {col} {dtype}"))
                logger.info(f"Added column financials.{col}")
        conn.commit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate()
    print("Migration complete.")
