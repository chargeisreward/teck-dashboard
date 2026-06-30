"""
SEC EDGAR CapEx 采集器 — Hyperscaler 真实资本开支

数据源: SEC EDGAR XBRL API（免费、官方）
- Microsoft/Google/Meta: 标准 us-gaap:PaymentsToAcquirePropertyPlantAndEquipment 概念
- Amazon: 标准概念在 2017 后停用，改从 10-K HTML 抓 "Purchases of property and equipment"

API 文档: https://www.sec.gov/edgar/sec-api-documentation

频率: 季度（10-Q 4-6 周一次），CapEx 是 AI 芯片需求最关键的领先指标：
HBM/CoWoS/先进封装 的需求直接由 hyperscaler CapEx 决定。
"""
import json
import logging
import re
import urllib.request
from datetime import date

from industry_collector.base import BaseCollector

logger = logging.getLogger(__name__)

# SEC EDGAR 严格要求 User-Agent 格式：Name email
SEC_USER_AGENT = "teck-dashboard research alex@example.com"
SEC_HEADERS = {"User-Agent": SEC_USER_AGENT}

# SEC EDGAR XBRL 概念路径
# 文档：https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json
SEC_BASE = "https://data.sec.gov/api/xbrl/companyconcept"


class _SecCapExBase(BaseCollector):
    """SEC EDGAR CapEx 采集的基类。

    各 hyperscaler 共享：
    - 同样的 XBRL 概念（us-gaap:PaymentsToAcquirePropertyPlantAndEquipment）
    - 同样的 JSON 结构 {"units": {"USD": [...]}, "label": ...}
    - 同样的 CapEx 数值字段（美元绝对值）
    """
    source = "sec_edgar_capex"
    unit = "US$B"
    category = "hyperscaler"
    category_cn = "超大规模云厂商"
    update_frequency = "quarterly"
    description = "季度资本开支，直接决定 HBM/CoWoS/先进封装 需求"
    collection_method = "SEC EDGAR XBRL API + 10-K HTML 解析"
    cik = ""                # 子类覆盖
    sec_concept = "PaymentsToAcquirePropertyPlantAndEquipment"

    def _fetch_xbrl_capex(self) -> list[dict]:
        """从 SEC EDGAR XBRL 拉取 CapEx 时间序列（USD 美元）。"""
        url = f"{SEC_BASE}/CIK{self.cik}/us-gaap/{self.sec_concept}.json"
        req = urllib.request.Request(url, headers=SEC_HEADERS)
        try:
            data = json.loads(urllib.request.urlopen(req, timeout=30).read())
        except Exception as e:
            logger.warning(f"SEC EDGAR fetch failed for {self.cik} / {self.sec_concept}: {e}")
            return []

        usd_entries = data.get("units", {}).get("USD", [])
        # SEC entries: {accn, cik, end, entityName, fp, form, fp, val, ...}
        # 过滤 fp 标记：fp='FY' 是年度（4 个季度合计），fp='Q1/Q2/Q3' 是单季
        # 我们要季度值 → fp starts with 'Q' OR form in ('10-K', '10-Q')
        return usd_entries

    def _latest_quarterly_value(self, entries: list[dict]) -> tuple[float, str, str] | None:
        """从 XBRL entries 提取最近一个季度的 (值, 期间结束日, 来源 form)。"""
        if not entries:
            return None
        # 取最近一条（end 日期最新）
        latest = entries[-1]
        return float(latest["val"]), latest["end"], latest.get("form", "")

    def _save_observation(self, value: float, period_end: str, source_url: str) -> dict:
        """写入 IndicatorObservation（值从 USD 美元换算为 亿美元）。"""
        if not self.db:
            return {"success": True, "value": value / 1e8, "date": period_end, "unit": "US$B"}

        ind = self._get_or_create_indicator(self.db)
        # CapEx 数值从 USD 美元 → 亿USD（/1e8）
        value_yi = round(value / 1e8, 2)
        return self._write_observation(
            self.db, ind.id, value_yi,
            target_date=period_end,
            note=f"From SEC EDGAR XBRL ({source_url}, form: {self._last_form})",
            data_quality="confirmed",  # SEC 是官方一手数据
        )


class _MicrosoftCapExBase(_SecCapExBase):
    """Microsoft (CIK 0000789019) - 共享 XBRL 路径"""
    cik = "0000789019"
    indicator_name = "msft_capex"
    indicator_name_cn = "Microsoft 资本开支"
    source_url = f"{SEC_BASE}/CIK0000789019/us-gaap/PaymentsToAcquirePropertyPlantAndEquipment.json"


class _GoogleCapExBase(_SecCapExBase):
    """Google/Alphabet (CIK 0001652044)"""
    cik = "0001652044"
    indicator_name = "goog_capex"
    indicator_name_cn = "Google 资本开支"
    source_url = f"{SEC_BASE}/CIK0001652044/us-gaap/PaymentsToAcquirePropertyPlantAndEquipment.json"


class _MetaCapExBase(_SecCapExBase):
    """Meta Platforms (CIK 0001326801)"""
    cik = "0001326801"
    indicator_name = "meta_capex"
    indicator_name_cn = "Meta 资本开支"
    source_url = f"{SEC_BASE}/CIK0001326801/us-gaap/PaymentsToAcquirePropertyPlantAndEquipment.json"


class _AmazonCapExBase(_SecCapExBase):
    """Amazon (CIK 0001018724) - 标准 XBRL 概念在 2017 后停用，
    改从最新 10-K HTML 抓 "Purchases of property and equipment, net of proceeds from incentive grants"
    """
    cik = "0001018724"
    indicator_name = "amzn_capex"
    indicator_name_cn = "Amazon 资本开支"
    # 走 10-K HTML 解析路径，sec_concept 留空
    sec_concept = ""

    def _fetch_xbrl_capex(self) -> list[dict]:
        # 不用 XBRL API（2017 后停用），改走 10-K 解析
        return self._parse_10k_capex()

    def _parse_10k_capex(self) -> list[dict]:
        """从 Amazon 最新 10-K HTML 解析 CapEx（"Purchases of property and equipment"）。
        返回结构：[{end, val, form}] 模仿 XBRL API。
        """
        try:
            # 用 submissions API 找最新 10-K
            url = f"https://data.sec.gov/submissions/CIK{self.cik}.json"
            req = urllib.request.Request(url, headers=SEC_HEADERS)
            data = json.loads(urllib.request.urlopen(req, timeout=30).read())

            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            accs = recent.get("accessionNumber", [])
            docs = recent.get("primaryDocument", [])
            dates = recent.get("filingDate", [])

            # 找最新一份 10-K
            for i, form in enumerate(forms):
                if form == "10-K":
                    acc = accs[i].replace("-", "")
                    doc = docs[i]
                    filing_url = f"https://www.sec.gov/Archives/edgar/data/1018724/{acc}/{doc}"
                    break
            else:
                logger.warning("No 10-K found for Amazon")
                return []

            html = urllib.request.urlopen(urllib.request.Request(filing_url, headers=SEC_HEADERS), timeout=30).read().decode("utf-8", errors="ignore")
            # 提取 "Purchases of property and equipment" 行
            # Amazon 10-K 格式: "Purchases of property and equipment ... $ 30,000"
            # 匹配：数字 + "  " 或 " (" 之间
            m = re.search(r'Purchases\s+of\s+property\s+and\s+equipment[^$]*?\$\s*([\d,]+)', html, re.IGNORECASE)
            if m:
                val = float(m.group(1).replace(",", ""))
                # 10-K 是年度数据，period_end 用 filing date 的 FY 末
                fy_date = f"{dates[i][:4]}-12-31"
                return [{"end": fy_date, "val": val, "form": "10-K"}]
            return []
        except Exception as e:
            logger.warning(f"Amazon 10-K parse failed: {e}")
            return []


# === 具体的 collector 类（每个继承对应基类） ===

class HyperscalerAmazonCapExCollector(_AmazonCapExBase):
    async def collect(self, db=None) -> dict:
        self.db = db
        entries = self._fetch_xbrl_capex()
        result = self._latest_quarterly_value(entries)
        if not result:
            return {"success": False, "error": "no_data", "source": self.source, "indicator": self.indicator_name}
        value, period_end, self._last_form = result[0], result[1], result[2]
        return self._save_observation(value, period_end, self.source_url)


class HyperscalerMicrosoftCapExCollector(_MicrosoftCapExBase):
    async def collect(self, db=None) -> dict:
        self.db = db
        entries = self._fetch_xbrl_capex()
        result = self._latest_quarterly_value(entries)
        if not result:
            return {"success": False, "error": "no_data", "source": self.source, "indicator": self.indicator_name}
        value, period_end, self._last_form = result[0], result[1], result[2]
        return self._save_observation(value, period_end, self.source_url)


class HyperscalerGoogleCapExCollector(_GoogleCapExBase):
    async def collect(self, db=None) -> dict:
        self.db = db
        entries = self._fetch_xbrl_capex()
        result = self._latest_quarterly_value(entries)
        if not result:
            return {"success": False, "error": "no_data", "source": self.source, "indicator": self.indicator_name}
        value, period_end, self._last_form = result[0], result[1], result[2]
        return self._save_observation(value, period_end, self.source_url)


class HyperscalerMetaCapExCollector(_MetaCapExBase):
    async def collect(self, db=None) -> dict:
        self.db = db
        entries = self._fetch_xbrl_capex()
        result = self._latest_quarterly_value(entries)
        if not result:
            return {"success": False, "error": "no_data", "source": self.source, "indicator": self.indicator_name}
        value, period_end, self._last_form = result[0], result[1], result[2]
        return self._save_observation(value, period_end, self.source_url)
