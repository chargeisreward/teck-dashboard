"""
DRAM 价格采集器（DDR4/DDR5 spot/contract）— TrendForce 公开页面

数据源: https://www.trendforce.com/price/dram/dram_spot + /dram_contract （公开 HTML）
覆盖：
- DDR5 16Gb (2Gx8) 4800/5600    # 主流 DDR5 PC/Server 单条
- DDR4 16Gb (2Gx8) 3200        # 主流 DDR4 PC 单条
- DDR5 16Gb eTT               # DDR5 embedded (服务器/汽车)
- DDR4 16Gb eTT               # DDR4 embedded

价格单位: 美元 / 16Gb chip (TrendForce 原始单位)。
我们转换为 美元/Gb (chip 价 ÷ 16) 以便跨产品比较。

频率: 每日（TrendForce 日级更新），cron 每天 1 次足够。
"""
import json
import logging
import re
import urllib.request
from datetime import date

from bs4 import BeautifulSoup

from industry_collector.base import BaseCollector

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (teck-dashboard research)"
TRENDFORCE_BASE = "https://www.trendforce.com"

# Target URL pattern (TrendForce public pricing pages)
URL_SPOT = f"{TRENDFORCE_BASE}/price/dram/dram_spot"
URL_CONTRACT = f"{TRENDFORCE_BASE}/price/dram/dram_contract"


def _fetch_dram_table_for_url(url: str) -> list[dict]:
    """从 TrendForce DRAM price 页面解析表格。模块级 helper（便于测试 import）。"""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        html = urllib.request.urlopen(req, timeout=30).read()
    except Exception as e:
        logger.warning(f"TrendForce fetch failed for {url}: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    result = []

    # 找所有含 16Gb 的 <tr>
    for tr in soup.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        if not cells or len(cells) < 2:
            continue
        item = cells[0]
        if "16Gb" not in item:
            continue
        try:
            avg_str = cells[5].replace(",", "")  # Session Average
            avg = float(avg_str)
        except (IndexError, ValueError):
            continue
        if avg <= 0:
            continue
        change_str = cells[6] if len(cells) > 6 else ""
        change_match = re.search(r"([-+]?\d+\.?\d*)", change_str.replace("▲", "").replace("▼", ""))
        change_pct = float(change_match.group(1)) if change_match else None
        result.append({
            "item": item,
            "url": url,
            "avg_usd_per_chip_16gb": avg,
            "change_pct": change_pct,
            "raw_cells": cells[:7],
        })
    return result


def _normalize_to_per_gb(per_16gb_chip: float) -> float:
    """Convert from $/16Gb chip → $/Gb."""
    return round(per_16gb_chip / 16.0, 4)


# Backwards-compat: 保留旧名（测试 import 它）
_fetch_dram_table = _fetch_dram_table_for_url


class _TrendForceDRAMBase(BaseCollector):
    """TrendForce DRAM 价格采集的基类。"""
    source = "trendforce_dram_price"
    unit = "USD/GB"
    category = "memory"
    category_cn = "内存/存储"
    update_frequency = "daily"
    description = "TrendForce 公开 DRAM 价格（16Gb chip 单价，已换算 $/GB）"
    collection_method = "TrendForce 公开 HTML scraping（dram_spot / dram_contract）"
    target_item = ""  # e.g. "DDR5 16Gb (2Gx8) 4800/5600"
    url = ""

    def _fetch_dram_table(self) -> list[dict]:
        """实例方法包装，使子类可 mock self._fetch_dram_table。"""
        return _fetch_dram_table_for_url(self.url)

    def _save(self, value: float, change_pct: float | None, raw_item: str) -> dict:
        """value 已经是 $/Gb。"""
        target_date = date.today().isoformat()
        if not getattr(self, "db", None):
            return {"success": True, "value": value, "unit": self.unit,
                    "date": target_date, "change_pct": change_pct,
                    "raw_item": raw_item}

        ind = self._get_or_create_indicator(self.db)
        change_note = f" Daily change {change_pct:+.2f}%" if change_pct is not None else ""
        note = f"TrendForce {self.url} — {raw_item}：${value}/GB.{change_note}"
        return self._write_observation(
            self.db, ind.id, value,
            target_date=target_date,
            note=note,
            data_quality="confirmed",  # TrendForce 是行业一手数据
        )


class DDR5SpotPriceCollector(_TrendForceDRAMBase):
    """DDR5 16Gb 4800/5600 — 主流 DDR5 单条现货价（反映最新 spot 市场）。"""
    indicator_name = "ddr5_16gb_spot_price"
    indicator_name_cn = "DDR5 16Gb 现货价"
    target_item = "DDR5 16Gb (2Gx8) 4800/5600"
    url = URL_SPOT

    async def collect(self, db=None) -> dict:
        self.db = db
        for row in self._fetch_dram_table():
            if row["item"] == self.target_item:
                per_gb = _normalize_to_per_gb(row["avg_usd_per_chip_16gb"])
                return self._save(per_gb, row["change_pct"], row["item"])
        return {"success": False, "error": "no_data",
                "source": self.source, "indicator": self.indicator_name}


class DDR5ContractPriceCollector(_TrendForceDRAMBase):
    """DDR5 16Gb eTT — embedded 合约价（服务器 / 汽车级）。"""
    indicator_name = "ddr5_16gb_ett_contract_price"
    indicator_name_cn = "DDR5 16Gb eTT 合约价"
    target_item = "DDR5 16Gb (2Gx8) eTT"
    url = URL_CONTRACT

    async def collect(self, db=None) -> dict:
        self.db = db
        for row in self._fetch_dram_table():
            if row["item"] == self.target_item:
                per_gb = _normalize_to_per_gb(row["avg_usd_per_chip_16gb"])
                return self._save(per_gb, row["change_pct"], row["item"])
        return {"success": False, "error": "no_data",
                "source": self.source, "indicator": self.indicator_name}


class DDR4SpotPriceCollector(_TrendForceDRAMBase):
    """DDR4 16Gb 3200 — 主流 DDR4 单条现货价（legacy 仍有需求）。"""
    indicator_name = "ddr4_16gb_spot_price"
    indicator_name_cn = "DDR4 16Gb 现货价"
    target_item = "DDR4 16Gb (2Gx8) 3200"
    url = URL_SPOT

    async def collect(self, db=None) -> dict:
        self.db = db
        for row in self._fetch_dram_table():
            if row["item"] == self.target_item:
                per_gb = _normalize_to_per_gb(row["avg_usd_per_chip_16gb"])
                return self._save(per_gb, row["change_pct"], row["item"])
        return {"success": False, "error": "no_data",
                "source": self.source, "indicator": self.indicator_name}


class DDR4ContractPriceCollector(_TrendForceDRAMBase):
    """DDR4 16Gb eTT — embedded 合约价。"""
    indicator_name = "ddr4_16gb_ett_contract_price"
    indicator_name_cn = "DDR4 16Gb eTT 合约价"
    target_item = "DDR4 16Gb (2Gx8) eTT"
    url = URL_CONTRACT

    async def collect(self, db=None) -> dict:
        self.db = db
        for row in self._fetch_dram_table():
            if row["item"] == self.target_item:
                per_gb = _normalize_to_per_gb(row["avg_usd_per_chip_16gb"])
                return self._save(per_gb, row["change_pct"], row["item"])
        return {"success": False, "error": "no_data",
                "source": self.source, "indicator": self.indicator_name}
