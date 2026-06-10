"""
TSMC IR 数据采集器
- 月度营收 (每月10日发布)
- CoWoS产能 / 利用率 / 3nm占比 (季度法说会)
"""

import re
import logging
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup

from industry_collector.base import BaseCollector

logger = logging.getLogger(__name__)

TSMC_REVENUE_URL = "https://investor.tsmc.com/english/monthly-revenue/2026"
TSMC_IR_URL = "https://investor.tsmc.com/english"


class TSMCMonthlyRevenueCollector(BaseCollector):
    """TSMC 月度营收采集器 — 每月10日发布前月数据"""

    source = "tsmc_ir"
    indicator_name = "tsmc_monthly_revenue"
    indicator_name_cn = "TSMC月度营收"
    unit = "亿NT$"
    category = "foundry"
    category_cn = "晶圆制造"
    update_frequency = "monthly"
    description = "TSMC每月10日发布前月合并营收(新台币亿元)，领先所有半导体季度财报1-2个月"
    source_url = TSMC_REVENUE_URL
    collection_method = "TSMC IR 网页 scraping"

    async def collect(self, db=None) -> dict:
        """采集最新月度营收数据"""
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }

        try:
            resp = requests.get(TSMC_REVENUE_URL, headers=headers, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"TSMC IR page fetch failed: {e}")
            return self._try_fallback(db=db)

        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator="\n")

        # Try to parse monthly revenue from the page
        # Pattern: look for revenue numbers in tables or text
        revenue_data = self._parse_monthly_revenue(text)

        if revenue_data:
            value = revenue_data["value"]
            month_str = revenue_data["date"]
            mom_pct = revenue_data.get("mom_pct")
            yoy_pct = revenue_data.get("yoy_pct")

            note_parts = []
            if mom_pct is not None:
                note_parts.append(f"MoM: {mom_pct:+.1f}%")
            if yoy_pct is not None:
                note_parts.append(f"YoY: {yoy_pct:+.1f}%")

            if db is None:
                return {
                    "success": True,
                    "value": value,
                    "date": month_str,
                    "unit": self.unit,
                    "change_pct": mom_pct,
                    "note": "; ".join(note_parts),
                }

            ind = self._get_or_create_indicator(db)
            return self._write_observation(
                db, ind.id, value,
                target_date=month_str,
                note="; ".join(note_parts) if note_parts else "",
                data_quality="confirmed",
            )

        # Fallback: search for TSMC revenue news
        return self._try_fallback(db=db)

    def _parse_monthly_revenue(self, text: str) -> dict | None:
        """
        解析TSMC IR页面的月度营收表格
        TSMC格式: Month | Net Revenue (NT$ million) | YoY Change
        """
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        # Try to find January-April 2026 data
        # Pattern: month name with revenue number in millions
        month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December']
        month_abbr = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        # Look for lines containing month names followed by revenue numbers
        for line in lines:
            for i, mname in enumerate(month_names + month_abbr):
                if mname in line:
                    # Extract numbers from this line
                    nums = re.findall(r'([\d,]+(?:\.\d+)?)', line)
                    if len(nums) >= 1:
                        # First large number is likely the revenue
                        for num_str in nums:
                            rev_val = float(num_str.replace(",", ""))
                            # TSMC monthly rev in NT$ millions, typically 300,000-500,000
                            if 100000 < rev_val < 1000000:
                                rev_date = f"2026-{(i % 12) + 1:02d}-01"
                                rev_100m = round(rev_val / 100, 2)  # Convert 百万NT$ → 亿NT$
                                return {"value": rev_100m, "date": rev_date}

        # Also handle "YTD Total" if it exists
        ytd_match = re.search(r'YTD.*?([\d,]+(?:\.\d+)?)', text, re.IGNORECASE)
        if ytd_match:
            ytd_val = float(ytd_match.group(1).replace(",", ""))
            if 100000 < ytd_val < 5000000:
                return {
                    "value": round(ytd_val / 100, 2),
                    "date": "2026-04-01",
                }

        return None

    def _try_fallback(self, db=None) -> dict:
        """
        Fallback: 使用已知的最新数据
        当网页抓取失败时返回提示
        """
        if db:
            ind = self._get_or_create_indicator(db)
        return {
            "success": False,
            "error": "网页抓取失败，无法获取TSMC月度营收数据",
            "source": self.source,
            "indicator": self.indicator_name,
        }


class TSMCCoWoSCollector(BaseCollector):
    """TSMC CoWoS产能 / 产能利用率 / 先进制程占比 — 季度法说会数据"""

    source = "tsmc_ir"
    indicator_name = "cowos_capacity"
    indicator_name_cn = "CoWoS先进封装产能"
    unit = "千片/月"
    category = "foundry"
    category_cn = "晶圆制造"
    update_frequency = "quarterly"
    description = "TSMC CoWoS月产能, 季度法说会更新, AI芯片最关键瓶颈指标"
    source_url = TSMC_IR_URL
    collection_method = "TSMC法说会纪要 + TrendForce交叉验证"

    async def collect(self, db=None) -> dict:
        """
        CoWoS产能数据从TrendForce新闻和法说会纪要获取
        实际实现将在二期完善
        """
        # For Phase 1, this collector serves as a placeholder
        # Real implementation will parse TSMC earnings call transcripts
        if db:
            ind = self._get_or_create_indicator(db)
        return {
            "success": False,
            "error": "待实现：CoWoS产能数据需从法说会纪要/新闻解析",
            "source": self.source,
            "indicator": self.indicator_name,
        }
