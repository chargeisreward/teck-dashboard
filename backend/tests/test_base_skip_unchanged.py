"""测试 BaseCollector skip_unchanged 行为。

对应 issue：情报页面 timeline 上 china_customs/nvidia_ir 同一 value
每天重复写入。修复后值未变应跳过。
"""
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from industry_collector.base import BaseCollector


class _DummyCollector(BaseCollector):
    """最小可用的 BaseCollector 子类。"""
    source = "test_source"
    indicator_name = "test_indicator"
    indicator_name_cn = "测试指标"
    unit = "unit"
    category = "test"
    category_cn = "测试"


def _make_db_with_obs(obs_list):
    """Mock 一个 db，observations 按日期排序返回。

    obs_list: list of (date, value) tuples (按日期升序)
    """
    from models import IndicatorObservation

    db = MagicMock()
    # 模拟 _get_previous_value / _last_observation_value 的行为
    sorted_obs = sorted(obs_list, key=lambda o: o[0])

    def query_side_effect(*args, **kwargs):
        q = MagicMock()
        # 按 date 过滤
        q.filter.return_value.order_by.return_value.first.return_value = (
            sorted_obs[-1] if sorted_obs else None
        )
        # has_data_for_date 检查
        existing_for_date = {}
        for d, v in obs_list:
            existing_for_date.setdefault(d, (d, v))
        q.filter.return_value.first.side_effect = lambda: None  # 默认无

        return q

    db.query.return_value = MagicMock()
    return db, sorted_obs


def test_skip_unchanged_writes_first_value():
    """第一条 obs：无 previous → 写入。"""
    c = _DummyCollector()
    db = MagicMock()
    # 无同日数据
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    # 模拟 add + commit
    db.add = MagicMock()
    db.commit = MagicMock()

    result = c._write_observation(db, indicator_id=1, value=32.0, target_date=date(2026, 6, 11))

    assert result["success"] is True
    assert result.get("skipped") is None
    assert db.add.called
    assert db.commit.called


def test_skip_unchanged_skips_when_value_same():
    """值未变：skip_unchanged=True（默认）→ 跳过。"""
    c = _DummyCollector()
    db = MagicMock()

    # 模拟已存在一条 obs: 2026-06-11 = 32
    last_obs = MagicMock()
    last_obs.date = date(2026, 6, 11)
    last_obs.value = 32.0
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = last_obs
    # 同日检查返回 None
    db.query.return_value.filter.return_value.first.return_value = None

    db.add = MagicMock()
    db.commit = MagicMock()

    result = c._write_observation(
        db, indicator_id=1, value=32.0, target_date=date(2026, 6, 12)
    )

    assert result["success"] is True
    assert result["skipped"] == "unchanged_value"
    assert result["last_value"] == 32.0
    assert result["last_date"] == "2026-06-11"
    assert not db.add.called  # 没写入新行
    assert not db.commit.called


def test_skip_unchanged_writes_when_value_changes():
    """值变化：正常写入 + 计算 change_pct。"""
    c = _DummyCollector()
    db = MagicMock()

    last_obs = MagicMock()
    last_obs.date = date(2026, 6, 11)
    last_obs.value = 32.0
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = last_obs
    db.query.return_value.filter.return_value.first.return_value = None

    db.add = MagicMock()
    db.commit = MagicMock()

    result = c._write_observation(
        db, indicator_id=1, value=33.0, target_date=date(2026, 6, 12)
    )

    assert result["success"] is True
    assert result.get("skipped") is None
    assert result["value"] == 33.0
    # change_pct = (33-32)/32 = 3.125 → round to 3.12
    assert abs(result["change_pct"] - 3.12) < 0.01
    assert db.add.called
    assert db.commit.called


def test_skip_unchanged_false_overrides():
    """skip_unchanged=False 强制写入（即使值未变）。"""
    c = _DummyCollector()
    db = MagicMock()

    last_obs = MagicMock()
    last_obs.date = date(2026, 6, 11)
    last_obs.value = 32.0
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = last_obs
    db.query.return_value.filter.return_value.first.return_value = None

    db.add = MagicMock()
    db.commit = MagicMock()

    result = c._write_observation(
        db, indicator_id=1, value=32.0, target_date=date(2026, 6, 12),
        skip_unchanged=False,
    )

    assert result["success"] is True
    assert result.get("skipped") is None
    assert db.add.called


def test_estimated_quality_still_blocked():
    """Guard 1 仍生效：estimated 写不进去。"""
    c = _DummyCollector()
    db = MagicMock()

    result = c._write_observation(
        db, indicator_id=1, value=32.0,
        target_date=date(2026, 6, 12),
        data_quality="estimated",
    )

    assert result["success"] is False
    assert result["error"] == "estimated_quality_blocked"


def test_same_date_idempotent_returns_existing():
    """同日已有数据 → 返回 existing（不改值）。"""
    c = _DummyCollector()
    db = MagicMock()

    existing = MagicMock()
    existing.value = 32.0
    existing.change_pct = 1.5
    existing.date = date(2026, 6, 12)

    # has_data_for_date 返回 existing
    db.query.return_value.filter.return_value.first.return_value = existing

    db.add = MagicMock()
    db.commit = MagicMock()

    result = c._write_observation(
        db, indicator_id=1, value=99.0,  # 不同值也无所谓：同日优先
        target_date=date(2026, 6, 12),
    )

    assert result["success"] is True
    assert result["note"] == "already_exists"
    assert result["value"] == 32.0  # 返回 existing, 不是 new value
    assert not db.add.called


def test_floating_point_tolerance():
    """浮点接近应识别为相同（如 32.0000000001 == 32）。"""
    c = _DummyCollector()
    db = MagicMock()

    last_obs = MagicMock()
    last_obs.date = date(2026, 6, 11)
    last_obs.value = 32.0
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = last_obs
    db.query.return_value.filter.return_value.first.return_value = None

    result = c._write_observation(
        db, indicator_id=1, value=32.0 + 1e-12, target_date=date(2026, 6, 12)
    )
    assert result.get("skipped") == "unchanged_value"

    result = c._write_observation(
        db, indicator_id=1, value=32.001, target_date=date(2026, 6, 13)
    )
    assert result.get("skipped") is None
    assert result["value"] == 32.001