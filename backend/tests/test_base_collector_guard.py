"""测试 BaseCollector._write_observation 的 estimated guard。

CLAUDE.md 第一条: "No mock/synthetic data"。
原代码允许 _write_observation(data_quality='estimated') 写入占位值，污染 DB。
修复后 estimated 写入必须被拒绝。
"""
import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

from industry_collector.base import BaseCollector


class _StubCollector(BaseCollector):
    source = "test_source"
    indicator_name = "test_indicator"
    indicator_name_cn = "测试指标"
    unit = "US$B"
    category = "test"
    category_cn = "测试"
    update_frequency = "monthly"
    description = "测试"


def _mock_db_no_existing_data():
    """返回带 indicator 但**无**已有数据的 mock db。"""
    db = MagicMock()
    # 用于 _get_or_create_indicator → 返回 indicator mock
    ind_obj = MagicMock()
    ind_obj.id = 1
    # 用于 _has_data_for_date → 返回 None（不存在）
    # MagicMock 默认就是 truthy，需要显式改 side_effect
    query_mock = MagicMock()
    # 区分两种 query 调用：
    # _get_or_create_indicator 查 KeyIndicator by name
    # _has_data_for_date 查 IndicatorObservation by indicator_id+date
    # 简单办法：让所有 first() 返回 None 表示无数据
    # 但 _get_or_create_indicator 用 filter+first 拿 indicator → 也返回 None
    # 此时 _get_or_create_indicator 会创建新 indicator (走 db.add 路径)
    db.query.return_value.filter.return_value.first.return_value = None
    # _get_previous_value 查 IndicatorObservation → 也 None
    db.add = MagicMock()  # 用于 add() IndicatorObservation
    db.commit = MagicMock()
    return db


def test_estimated_write_is_blocked():
    """estimated 数据应被拒绝，不写入 DB。"""
    db = _mock_db_no_existing_data()
    collector = _StubCollector()

    result = collector._write_observation(
        db, indicator_id=1, value=42.0,
        target_date="2026-01-01", note="估算", data_quality="estimated",
    )

    assert result["success"] is False
    assert result["error"] == "estimated_quality_blocked"
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_confirmed_write_proceeds():
    """confirmed 数据应正常写入。"""
    db = _mock_db_no_existing_data()
    collector = _StubCollector()

    result = collector._write_observation(
        db, indicator_id=1, value=42.0,
        target_date="2026-01-01", note="实测", data_quality="confirmed",
    )

    assert result["success"] is True
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_official_write_proceeds():
    """official (FRED 等) 数据应正常写入。"""
    db = _mock_db_no_existing_data()
    collector = _StubCollector()

    result = collector._write_observation(
        db, indicator_id=1, value=4.5,
        target_date="2026-01-01", note="FRED", data_quality="official",
    )

    assert result["success"] is True


def test_default_quality_is_confirmed():
    """_write_observation 不传 data_quality 时默认是 confirmed（不是 estimated）。"""
    db = _mock_db_no_existing_data()
    collector = _StubCollector()

    added_obs = None
    def capture_add(obs):
        nonlocal added_obs
        added_obs = obs
    db.add.side_effect = capture_add

    collector._write_observation(
        db, indicator_id=1, value=42.0, target_date="2026-01-01",
    )

    assert added_obs is not None
    assert added_obs.data_quality == "confirmed"


def test_estimated_block_does_not_pollute_existing_rows():
    """estimated 写入失败时，不影响已存在的 confirmed 行。"""
    db = _mock_db_no_existing_data()
    collector = _StubCollector()

    r1 = collector._write_observation(
        db, indicator_id=1, value=42.0,
        target_date="2026-01-01", data_quality="estimated",
    )
    assert r1["success"] is False

    r2 = collector._write_observation(
        db, indicator_id=1, value=50.0,
        target_date="2026-01-01", data_quality="confirmed",
    )
    assert r2["success"] is True