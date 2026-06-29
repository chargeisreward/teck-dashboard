import pytest
from sqlalchemy import create_engine, inspect, String, Float
from database import Base
import models  # noqa: F401 — registers all tables on Base.metadata
import importlib.util
import sys
import types
from pathlib import Path


@pytest.fixture
def test_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


def test_new_tables_exist(test_engine):
    inspector = inspect(test_engine)
    tables = inspector.get_table_names()
    assert "fx_rate_cache" in tables
    assert "overseas_financial_updates" in tables
    assert "company_valuation_snapshots" in tables


def test_financial_columns_exist(test_engine):
    inspector = inspect(test_engine)
    columns = {c["name"]: c for c in inspector.get_columns("financials")}
    assert "currency" in columns
    assert "fx_rate" in columns
    assert "original_revenue" in columns
    assert "original_net_income" in columns
    assert isinstance(columns["currency"]["type"], String)
    assert isinstance(columns["fx_rate"]["type"], Float)
    assert isinstance(columns["original_revenue"]["type"], Float)
    assert isinstance(columns["original_net_income"]["type"], Float)


def test_migration_script_is_idempotent(test_engine):
    """调用迁移脚本，验证它不会抛出异常，且新表/列存在（幂等）。"""
    spec = importlib.util.spec_from_file_location(
        "migration_001",
        Path(__file__).resolve().parent.parent / "migrations" / "001_add_overseas_financial_columns.py",
    )
    migration = importlib.util.module_from_spec(spec)
    # Patch engine before loading/executing
    sys.modules["database"] = types.ModuleType("database")
    sys.modules["database"].engine = test_engine
    spec.loader.exec_module(migration)
    migration.migrate()
    migration.migrate()  # idempotent: second run should also succeed

    inspector = inspect(test_engine)
    assert "company_valuation_snapshots" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("financials")}
    assert "currency" in cols
