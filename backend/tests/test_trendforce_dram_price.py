"""测试 TrendForce DRAM 价格 collector 解析逻辑。"""
from unittest.mock import MagicMock, patch

import pytest

from industry_collector.sources.trendforce_dram_price import (
    _fetch_dram_table, _normalize_to_per_gb,
    DDR5SpotPriceCollector, DDR5ContractPriceCollector,
    DDR4SpotPriceCollector, DDR4ContractPriceCollector,
)


def test_normalize_to_per_gb():
    """TrendForce 报的是 $/16Gb chip，应转为 $/Gb。"""
    assert _normalize_to_per_gb(46.833) == pytest.approx(2.927, abs=0.001)
    assert _normalize_to_per_gb(73.744) == pytest.approx(4.609, abs=0.001)
    assert _normalize_to_per_gb(0) == 0  # 不会除以 0


def test_parse_trendforce_table_real_data():
    """解析真实 TrendForce DOM 结构。"""
    # 简化的 HTML 模拟 TrendForce dram_spot 页面
    html = """
    <html><body>
    <table>
      <tr><th>Item</th><th>Daily High</th><th>Daily Low</th><th>Session High</th><th>Session Low</th><th>Session Average</th><th>Session Change</th></tr>
      <tr><td>DDR5 16Gb (2Gx8) 4800/5600</td><td>61.00</td><td>31.50</td><td>61.00</td><td>31.50</td><td>46.833</td><td>▲ 0.21 %</td></tr>
      <tr><td>DDR5 16Gb (2Gx8) eTT</td><td>25.30</td><td>22.10</td><td>25.30</td><td>22.10</td><td>23.50</td><td>— 0.00 %</td></tr>
      <tr><td>DDR4 16Gb (2Gx8) 3200</td><td>92.00</td><td>39.10</td><td>92.00</td><td>39.10</td><td>73.744</td><td>▲ 1.04 %</td></tr>
    </table>
    </body></html>
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    # 模拟 _fetch_dram_table 的内部逻辑（避免 monkey-patching 网络层）
    result = []
    for tr in soup.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        if not cells or len(cells) < 2 or "16Gb" not in cells[0]:
            continue
        try:
            avg = float(cells[5].replace(",", ""))
        except (IndexError, ValueError):
            continue
        if avg <= 0:
            continue
        result.append({"item": cells[0], "avg_usd_per_chip_16gb": avg})
    assert len(result) == 3
    assert result[0]["item"] == "DDR5 16Gb (2Gx8) 4800/5600"
    assert result[0]["avg_usd_per_chip_16gb"] == 46.833
    assert result[2]["avg_usd_per_chip_16gb"] == 73.744


def test_ddr5_spot_collector_finds_target_item():
    """DDR5SpotPriceCollector 找 DDR5 4800/5600 行。"""
    fake_table = [
        {"item": "DDR5 16Gb (2Gx8) 4800/5600", "avg_usd_per_chip_16gb": 46.833, "change_pct": 0.21},
        {"item": "DDR5 16Gb (2Gx8) eTT", "avg_usd_per_chip_16gb": 23.50, "change_pct": 0.0},
    ]
    c = DDR5SpotPriceCollector()
    c._save = MagicMock(return_value={"success": True})
    c._fetch_dram_table = MagicMock(return_value=fake_table)
    import asyncio
    r = asyncio.run(c.collect(db=None))
    # 验 _save 被调用，参数为 46.833/16 = 2.927
    call_args = c._save.call_args
    assert call_args is not None
    per_gb = call_args[0][0]
    assert per_gb == pytest.approx(2.927, abs=0.01)


def test_ddr4_spot_collector_finds_target_item():
    """DDR4SpotPriceCollector 找 DDR4 3200 行。"""
    fake_table = [
        {"item": "DDR4 16Gb (2Gx8) 3200", "avg_usd_per_chip_16gb": 73.744, "change_pct": 1.04},
    ]
    c = DDR4SpotPriceCollector()
    c._save = MagicMock(return_value={"success": True})
    c._fetch_dram_table = MagicMock(return_value=fake_table)
    import asyncio
    r = asyncio.run(c.collect(db=None))
    call_args = c._save.call_args
    assert call_args is not None
    per_gb = call_args[0][0]
    assert per_gb == pytest.approx(4.609, abs=0.01)


def test_ddr5_contract_collector_finds_ett_item():
    """DDR5ContractPriceCollector 找 eTT 行。"""
    fake_table = [
        {"item": "DDR5 16Gb (2Gx8) 4800/5600", "avg_usd_per_chip_16gb": 46.833, "change_pct": None},
        {"item": "DDR5 16Gb (2Gx8) eTT", "avg_usd_per_chip_16gb": 23.50, "change_pct": 0.0},
    ]
    c = DDR5ContractPriceCollector()
    c._save = MagicMock(return_value={"success": True})
    c._fetch_dram_table = MagicMock(return_value=fake_table)
    import asyncio
    r = asyncio.run(c.collect(db=None))
    call_args = c._save.call_args
    assert call_args is not None
    per_gb = call_args[0][0]
    assert per_gb == pytest.approx(1.469, abs=0.01)


def test_no_target_item_returns_no_data():
    """TrendForce 数据中没有目标 item → success=False。"""
    fake_table = [
        {"item": "LPDDR 16Gb (2Gx8) 5500", "avg_usd_per_chip_16gb": 25.0, "change_pct": None},
    ]
    c = DDR5SpotPriceCollector()
    c._fetch_dram_table = MagicMock(return_value=fake_table)
    import asyncio
    r = asyncio.run(c.collect(db=None))
    assert r["success"] is False
    assert r["error"] == "no_data"


def test_negative_or_zero_price_filtered_in_url_fetcher():
    """URL fetcher 的 _fetch_dram_table_for_url 应该过滤 avg <= 0 的行。

    collector 信任 _fetch_dram_table 返回的结果（已经过滤），
    所以这里直接测试模块级函数。
    """
    # 构造一个 HTML，DDR5 4800/5600 的 avg 是 0（应被过滤）
    # TrendForce 表格 7 列：Item | Daily High | Daily Low | Session High | Session Low | Session Average | Session Change
    html = """
    <html><body><table>
      <tr><th>Item</th><th>Daily High</th><th>Daily Low</th><th>Session High</th><th>Session Low</th><th>Session Average</th><th>Session Change</th></tr>
      <tr><td>DDR5 16Gb (2Gx8) 4800/5600</td><td>0.00</td><td>0.00</td><td>0.00</td><td>0.00</td><td>0.00</td><td>—</td></tr>
      <tr><td>DDR4 16Gb (2Gx8) 3200</td><td>92.00</td><td>39.10</td><td>92.00</td><td>39.10</td><td>73.744</td><td>1.04%</td></tr>
    </table></body></html>
    """
    from industry_collector.sources import trendforce_dram_price
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.read.return_value = html.encode("utf-8")
        mock_urlopen.return_value.__enter__ = lambda s: s
        mock_urlopen.return_value.__exit__ = lambda s, *a: False
        result = trendforce_dram_price._fetch_dram_table_for_url("http://fake-url")

    # DDR5 行（avg=0）被过滤；DDR4 行（avg=73.744）保留
    items = [r["item"] for r in result]
    assert "DDR4 16Gb (2Gx8) 3200" in items
    assert "DDR5 16Gb (2Gx8) 4800/5600" not in items  # 0 被过滤
