"""测试 Vantage.sh GPU 价格 collector 解析逻辑。"""
import json
from unittest.mock import patch, MagicMock

import pytest

from industry_collector.sources.vantage_gpu_price import (
    H100SingleGPUPriceCollector, H100EightGPUPriceCollector,
    H200EightGPUPriceCollector, B200EightGPUPriceCollector,
    A100EightGPUPriceCollector, VANTAGE_INSTANCES_URL,
)

# 模拟 Vantage.sh API 返回的精简数据
SAMPLE_VANTAGE = [
    {
        "instance_type": "p5.4xlarge", "GPU_model": "NVIDIA H100", "GPU": 1,
        "pricing": {"us-east-1": {"linux": {"ondemand": "6.88"}}}
    },
    {
        "instance_type": "p5.48xlarge", "GPU_model": "NVIDIA H100", "GPU": 8,
        "pricing": {"us-east-1": {"linux": {"ondemand": "55.04"}}}
    },
    {
        "instance_type": "p5en.48xlarge", "GPU_model": "NVIDIA H200", "GPU": 8,
        "pricing": {"us-east-1": {"linux": {"ondemand": "63.296"}}}
    },
    {
        "instance_type": "p6-b200.48xlarge", "GPU_model": "NVIDIA B200", "GPU": 8,
        "pricing": {"us-east-1": {"linux": {"ondemand": "113.9328"}}}
    },
    {
        "instance_type": "p4d.24xlarge", "GPU_model": "NVIDIA A100", "GPU": 8,
        "pricing": {"us-east-1": {"linux": {"ondemand": "21.957642"}}}
    },
]


def _mock_urlopen_response(data):
    """构造 urlopen 的 mock 返回值。"""
    m = MagicMock()
    m.read.return_value = json.dumps(data).encode("utf-8")
    m.__enter__ = MagicMock(return_value=m)
    m.__exit__ = MagicMock(return_value=False)
    return m


def test_h100_single_gpu_price_parsing():
    """H100 1卡：实例 $6.88/hr → per-GPU $6.88/(GPU·hr)。"""
    c = H100SingleGPUPriceCollector()
    c._fetch_vantage_data = MagicMock(return_value=SAMPLE_VANTAGE)
    result = c._extract_target_price(SAMPLE_VANTAGE)
    assert result is not None
    price, gpu_model = result
    assert price == 6.88
    assert "H100" in gpu_model


def test_h100_eight_gpu_price_parsing():
    """H100 8卡：实例 $55.04/hr → per-GPU $6.88/(GPU·hr)。"""
    c = H100EightGPUPriceCollector()
    c._fetch_vantage_data = MagicMock(return_value=SAMPLE_VANTAGE)
    result = c._extract_target_price(SAMPLE_VANTAGE)
    assert result is not None
    price, _ = result
    assert price == 55.04
    # per-GPU = 55.04 / 8 = 6.88
    assert c._save_price(price)["value"] == pytest.approx(6.88, abs=0.01)


def test_h200_eight_gpu_price_parsing():
    """H200 8卡：$63.30/hr → $7.91/GPU/h。"""
    c = H200EightGPUPriceCollector()
    c._fetch_vantage_data = MagicMock(return_value=SAMPLE_VANTAGE)
    result = c._extract_target_price(SAMPLE_VANTAGE)
    assert result is not None
    price, _ = result
    assert price == 63.296
    assert c._save_price(price)["value"] == pytest.approx(7.912, abs=0.01)


def test_b200_eight_gpu_price_parsing():
    """B200 8卡：$113.93/hr → $14.24/GPU/h。"""
    c = B200EightGPUPriceCollector()
    c._fetch_vantage_data = MagicMock(return_value=SAMPLE_VANTAGE)
    result = c._extract_target_price(SAMPLE_VANTAGE)
    assert result is not None
    price, _ = result
    assert price == 113.9328
    assert c._save_price(price)["value"] == pytest.approx(14.24, abs=0.01)


def test_a100_eight_gpu_price_parsing():
    """A100 8卡：$21.96/hr → $2.74/GPU/h。"""
    c = A100EightGPUPriceCollector()
    c._fetch_vantage_data = MagicMock(return_value=SAMPLE_VANTAGE)
    result = c._extract_target_price(SAMPLE_VANTAGE)
    assert result is not None
    price, _ = result
    assert price == pytest.approx(21.9576, abs=0.001)


def test_missing_instance_returns_none():
    """目标 instance_type 不在 Vantage.sh 数据中 → 返回 None。"""
    c = H100SingleGPUPriceCollector()
    empty_data = []
    assert c._extract_target_price(empty_data) is None


def test_missing_us_east_1_region_returns_none():
    """目标 instance 存在但没 us-east-1 region → 返回 None。"""
    c = H100SingleGPUPriceCollector()
    data = [
        {
            "instance_type": "p5.4xlarge", "GPU_model": "NVIDIA H100", "GPU": 1,
            "pricing": {"eu-west-1": {"linux": {"ondemand": "6.88"}}}  # 只有 eu-west-1
        }
    ]
    assert c._extract_target_price(data) is None


def test_no_data_response_triggers_failure():
    """_fetch_vantage_data 返回空列表 → collect 返回 success=False。"""
    import asyncio
    c = H100SingleGPUPriceCollector()
    c._fetch_vantage_data = MagicMock(return_value=[])
    r = asyncio.run(c.collect(db=None))
    assert r["success"] is False
    assert r["error"] == "no_data"


def test_vantage_url_uses_https():
    """确保使用 HTTPS URL（Vantage.sh 只在 https 下提供）。"""
    assert VANTAGE_INSTANCES_URL.startswith("https://")
    assert "vantage.sh" in VANTAGE_INSTANCES_URL
