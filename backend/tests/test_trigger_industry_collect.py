"""测试 trigger_industry_collect 中 TimelineEvent 创建逻辑。

核心验证：collector 返回 unchanged_value / already_exists 时，
不创建 TimelineEvent，避免 timeline 被重复刷屏。
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from industry_collector.base import BaseCollector


class _StubCollector(BaseCollector):
    source = "stub"
    indicator_name = "stub_indicator"
    indicator_name_cn = "测试指标"
    unit = "US$B"
    category = "test"
    category_cn = "测试"

    async def collect(self, db=None):
        return {"success": True, "value": 32.0}


def _build_mock_db(last_obs=None, existing_tl=None):
    """构造一个够用的 mock DB。"""
    db = MagicMock()

    # KeyIndicator
    ind_obj = MagicMock()
    ind_obj.id = 1
    ind_obj.name = "stub_indicator"
    ind_obj.name_cn = "测试指标"
    ind_obj.unit = "US$B"
    ind_obj.source = "stub"
    ind_obj.description = "desc"

    # indicator query
    def query_side_effect(model):
        q = MagicMock()
        if model.__name__ == "KeyIndicator":
            q.filter.return_value.first.return_value = ind_obj
        elif model.__name__ == "IndicatorObservation":
            q.filter.return_value.order_by.return_value.first.return_value = last_obs
            # 第二个 filter 给 existing_tl
            q.filter.return_value.first.return_value = existing_tl
        elif model.__name__ == "TimelineEvent":
            q.filter.return_value.first.return_value = existing_tl
        return q

    db.query.side_effect = query_side_effect
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    return db, ind_obj


@patch("main.run_industry_collectors")
def test_skipped_unchanged_value_no_timeline(mock_run_collectors):
    """unchanged_value 时不创建 TimelineEvent。"""
    from main import trigger_industry_collect

    db, _ = _build_mock_db()
    mock_run_collectors.return_value = {
        "success": [{
            "source": "stub",
            "indicator": "stub_indicator",
            "result": {
                "success": True,
                "skipped": "unchanged_value",
                "value": 32.0,
            },
        }],
        "errors": [],
    }

    resp = trigger_industry_collect(db=db)

    assert resp["timeline_created"] == 0
    assert resp["collected"] == 1
    db.add.assert_not_called()


@patch("main.run_industry_collectors")
def test_skipped_already_exists_no_timeline(mock_run_collectors):
    """already_exists 时不创建 TimelineEvent。"""
    from main import trigger_industry_collect

    db, _ = _build_mock_db()
    mock_run_collectors.return_value = {
        "success": [{
            "source": "stub",
            "indicator": "stub_indicator",
            "result": {
                "success": True,
                "note": "already_exists",
                "skipped": "already_exists",
                "value": 32.0,
            },
        }],
        "errors": [],
    }

    resp = trigger_industry_collect(db=db)

    assert resp["timeline_created"] == 0
    assert resp["collected"] == 1
    db.add.assert_not_called()


@patch("main.run_industry_collectors")
def test_new_observation_creates_timeline(mock_run_collectors):
    """真正新写入的 observation 才创建 TimelineEvent。"""
    from main import trigger_industry_collect

    last_obs = MagicMock()
    last_obs.id = 42
    last_obs.value = 33.0
    last_obs.change_pct = 3.12
    db, _ = _build_mock_db(last_obs=last_obs)

    mock_run_collectors.return_value = {
        "success": [{
            "source": "stub",
            "indicator": "stub_indicator",
            "result": {
                "success": True,
                "value": 33.0,
                "change_pct": 3.12,
            },
        }],
        "errors": [],
    }

    resp = trigger_industry_collect(db=db)

    assert resp["timeline_created"] == 1
    assert db.add.called
    # 验证 TimelineEvent 对象字段
    tl = db.add.call_args[0][0]
    assert tl.event_type == "collection"
    assert tl.indicator_name_cn == "测试指标"
    assert tl.value_display == "33.0 US$B (+3.1%)"


@patch("main.run_industry_collectors")
def test_existing_timeline_for_observation_skips(mock_run_collectors):
    """同一 observation 已有 TimelineEvent → 不重复创建。"""
    from main import trigger_industry_collect

    last_obs = MagicMock()
    last_obs.id = 42
    last_obs.value = 33.0
    last_obs.change_pct = None
    db, _ = _build_mock_db(last_obs=last_obs, existing_tl=MagicMock())

    mock_run_collectors.return_value = {
        "success": [{
            "source": "stub",
            "indicator": "stub_indicator",
            "result": {
                "success": True,
                "value": 33.0,
            },
        }],
        "errors": [],
    }

    resp = trigger_industry_collect(db=db)
    assert resp["timeline_created"] == 0


def test_skip_unchanged_is_default_in_base():
    """确认 BaseCollector 默认 skip_unchanged=True。"""
    import inspect
    sig = inspect.signature(BaseCollector._write_observation)
    assert sig.parameters["skip_unchanged"].default is True