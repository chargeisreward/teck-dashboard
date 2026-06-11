"""Migration: add data_source/last_verified columns and DataSource table"""
from database import engine, Base
from models import DataSource
from sqlalchemy import text, inspect

def column_exists(table, column):
    """Check if a column exists in a SQLite table."""
    insp = inspect(engine)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols

def migrate():
    # Create new DataSource table (safe, uses CREATE TABLE IF NOT EXISTS)
    DataSource.__table__.create(engine, checkfirst=True)

    # Add columns to industry_chain_links
    with engine.connect() as conn:
        if not column_exists("industry_chain_links", "data_source"):
            conn.execute(text("ALTER TABLE industry_chain_links ADD COLUMN data_source VARCHAR"))
            print("  + Added data_source to industry_chain_links")
        if not column_exists("industry_chain_links", "last_verified"):
            conn.execute(text("ALTER TABLE industry_chain_links ADD COLUMN last_verified DATE"))
            print("  + Added last_verified to industry_chain_links")

        if not column_exists("company_chain_links", "data_source"):
            conn.execute(text("ALTER TABLE company_chain_links ADD COLUMN data_source VARCHAR"))
            print("  + Added data_source to company_chain_links")
        if not column_exists("company_chain_links", "last_verified"):
            conn.execute(text("ALTER TABLE company_chain_links ADD COLUMN last_verified DATE"))
            print("  + Added last_verified to company_chain_links")

        if not column_exists("financials", "data_source"):
            conn.execute(text("ALTER TABLE financials ADD COLUMN data_source VARCHAR"))
            print("  + Added data_source to financials")
        if not column_exists("financials", "last_verified"):
            conn.execute(text("ALTER TABLE financials ADD COLUMN last_verified DATE"))
            print("  + Added last_verified to financials")

        conn.commit()

    print("Migration complete.")

if __name__ == "__main__":
    migrate()
