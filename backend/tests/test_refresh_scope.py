"""测试 refresh_all_company_data 覆盖范围：

之前 refresh 只遍历 CompanyChainLink 里的公司，导致 company_type='application' 但无 chain link 的公司
（META/TSLA/XIACF/MPNGY/PDD 等）从不被刷新。结果 dashboard overview 的"应用厂商"卡片没数据。

修复后 refresh 应遍历所有有 ticker 的 Company，不限 chain link 成员身份。
"""
import sqlite3
from unittest.mock import patch

import pytest

import refresh_company_data as rcd
from models import Company, StockInfoCache


def test_refresh_covers_non_chainlinked_companies(db, monkeypatch):
    """应用厂商类型公司即使不在 CompanyChainLink 里，也应被 refresh。"""
    # 一个有 chain link 的常规公司
    chain_co = Company(name="NVIDIA", ticker="NVDA", company_type="chip_design", sector="GPU")
    # 一个无 chain link 但有 ticker 的应用厂商
    orphan_co = Company(name="Tesla", ticker="TSLA", company_type="application", sector="EV/AI")
    db.add_all([chain_co, orphan_co])
    db.flush()

    # Mock 所有外部调用，让 refresh 直接走"成功"路径
    monkeypatch.setattr(rcd, "_parse_tencent_quote", lambda t: {
        "current_price": 100.0, "change_pct": 1.0, "market_cap_b": 500.0, "pe_ttm": 20.0,
        "source": "tencent",
    })
    monkeypatch.setattr(rcd, "_get_yfinance_info", lambda t: None)  # rate-limited
    monkeypatch.setattr(rcd, "HAS_YFINANCE", False)

    result = rcd.refresh_all_company_data(db)

    # 两个公司都应被更新，不只是 chain_co
    assert result["updated"] == 2, f"应刷新 2 家公司，实际 {result['updated']}"

    # 两个 ticker 都应有 cache
    for ticker in ("NVDA", "TSLA"):
        cache = db.query(StockInfoCache).filter_by(ticker=ticker).first()
        assert cache is not None, f"{ticker} 没被刷新"
        assert cache.data_json.get("source") == "tencent"


def test_refresh_skips_companies_without_ticker(db, monkeypatch):
    """无 ticker 的公司根本不会被迭代（query 过滤了），不会被"刷新"也不会被计入 skipped。"""
    no_ticker_co = Company(name="MyCo", ticker=None, company_type="other", sector="X")
    db.add(no_ticker_co)
    db.flush()

    monkeypatch.setattr(rcd, "_parse_tencent_quote", lambda t: None)
    monkeypatch.setattr(rcd, "HAS_YFINANCE", False)

    result = rcd.refresh_all_company_data(db)
    # 无 ticker 公司在 query 阶段被过滤，根本不会进入循环
    assert result["skipped"] == 0
    assert result["updated"] == 0


def test_refresh_orphan_gets_correct_data_source(db, monkeypatch):
    """未上链的 application 公司应被记 source='tencent'（若 Tencent 返回了数据）。"""
    co = Company(name="Meta", ticker="META", company_type="application", sector="AI/Social")
    db.add(co)
    db.flush()

    monkeypatch.setattr(rcd, "_parse_tencent_quote", lambda t: {
        "current_price": 565.0, "change_pct": 2.5,
        "market_cap_b": 14300.0, "pe_ttm": 25.0, "source": "tencent",
    })
    monkeypatch.setattr(rcd, "HAS_YFINANCE", False)

    rcd.refresh_all_company_data(db)

    cache = db.query(StockInfoCache).filter_by(ticker="META").first()
    assert cache is not None
    assert cache.data_json["source"] == "tencent"
    assert cache.data_json["market_cap_b"] == 14300.0
    assert cache.data_json["change_pct"] == 2.5