"""
BaseCollector — 产业数据采集器基类

职责:
1. 幂等采集检查 (同一指标同一天不重复)
2. 自动创建/查找 KeyIndicator 记录
3. 写入 IndicatorObservation + 自动计算边际变化
4. 来源标注 + 数据质量标注
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BaseCollector:
    """所有采集器的基类"""

    # 子类需覆盖以下字段
    source: str = ""                     # 数据源标识 (tsmc_ir, trendforce, ...)
    indicator_name: str = ""             # 指标英文名 (tsmc_monthly_revenue)
    indicator_name_cn: str = ""          # 指标中文名 (TSMC月度营收)
    unit: str = ""                       # 单位 (亿NT$, US$B, ...)
    category: str = ""                   # 供应链位置 (raw_materials, equipment, eda, chip_design, foundry, memory, packaging, distribution, end_market, gpu_cloud)
    category_cn: str = ""                # 供应链位置中文
    update_frequency: str = ""           # 更新频率 (monthly, quarterly, weekly, irregular)
    description: str = ""                # 指标描述
    source_url: str = ""                 # 数据源URL
    collection_method: str = ""          # 采集方法描述

    async def collect(self, db=None) -> dict:
        """
        采集主入口。
        返回: {"success": bool, "value": float, "date": str, "unit": str, "change_pct": float}
        """
        raise NotImplementedError

    def _get_or_create_indicator(self, db):
        """查找或创建 KeyIndicator 记录"""
        from models import KeyIndicator

        ind = db.query(KeyIndicator).filter(
            KeyIndicator.name == self.indicator_name
        ).first()

        if not ind:
            ind = KeyIndicator(
                name=self.indicator_name,
                name_cn=self.indicator_name_cn,
                unit=self.unit,
                source=self.source,
                source_url=self.source_url,
                category=self.category,
                description=self.description,
                is_automated=True,
                update_frequency=self.update_frequency,
                collection_method=self.collection_method,
            )
            db.add(ind)
            db.flush()
            logger.info(f"Created new indicator: {self.indicator_name}")

        return ind

    def _has_today_data(self, db, indicator_id: int) -> bool:
        """检查当天是否已有数据（幂等保护）"""
        from models import IndicatorObservation
        today = date.today()
        existing = db.query(IndicatorObservation).filter(
            IndicatorObservation.indicator_id == indicator_id,
            IndicatorObservation.date == today,
        ).first()
        return existing is not None

    def _has_data_for_date(self, db, indicator_id: int, target_date) -> bool:
        """检查指定日期是否已有数据"""
        from models import IndicatorObservation
        if isinstance(target_date, str):
            target_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        existing = db.query(IndicatorObservation).filter(
            IndicatorObservation.indicator_id == indicator_id,
            IndicatorObservation.date == target_date,
        ).first()
        return existing is not None

    def _get_previous_value(self, db, indicator_id: int) -> Optional[float]:
        """获取最近一次观测值（用于计算变化率）"""
        from models import IndicatorObservation
        last = db.query(IndicatorObservation).filter(
            IndicatorObservation.indicator_id == indicator_id
        ).order_by(IndicatorObservation.date.desc()).first()

        if last:
            return last.value
        return None

    def _compute_change_pct(self, current: float, previous: Optional[float]) -> Optional[float]:
        """计算变化百分比"""
        if previous is None or previous == 0:
            return None
        return round((current - previous) / previous * 100, 2)

    def _write_observation(
        self, db, indicator_id: int,
        value: float,
        target_date=None,
        note: str = "",
        data_quality: str = "confirmed",
    ) -> dict:
        """
        写入观测值 + 自动计算边际变化
        Returns: {"success": True, "value": ..., "change_pct": ..., "date": ...}

        Guard: 拒绝 data_quality='estimated' 写入。CLAUDE.md 第一条：
        "No mock/synthetic data"。estimated 数据会污染 DB，宁可报错失败。
        """
        from models import IndicatorObservation

        # === Guard: estimated 禁止写入 ===
        if data_quality == "estimated":
            logger.error(
                f"BLOCKED estimated write: {self.indicator_name}={value} {self.unit}. "
                f"请实现真实数据源或删除此 collector。 "
                f"详见 CLAUDE.md 'No mock/synthetic data'。"
            )
            return {
                "success": False,
                "error": "estimated_quality_blocked",
                "source": self.source,
                "indicator": self.indicator_name,
                "note": (
                    f"value={value} 未写入。estimated 数据禁止入库。 "
                    f"请实现真实抓取或删除 collector。"
                ),
            }

        if target_date is None:
            target_date = date.today()
        elif isinstance(target_date, str):
            target_date = datetime.strptime(target_date, "%Y-%m-%d").date()

        # 幂等检查
        if self._has_data_for_date(db, indicator_id, target_date):
            logger.info(f"Data already exists for {self.indicator_name} on {target_date}, skipping")
            existing = db.query(IndicatorObservation).filter(
                IndicatorObservation.indicator_id == indicator_id,
                IndicatorObservation.date == target_date,
            ).first()
            return {
                "success": True,
                "value": existing.value,
                "change_pct": existing.change_pct,
                "date": str(target_date),
                "note": "already_exists",
            }

        previous_value = self._get_previous_value(db, indicator_id)
        change_pct = self._compute_change_pct(value, previous_value)

        obs = IndicatorObservation(
            indicator_id=indicator_id,
            date=target_date,
            value=value,
            previous_value=previous_value,
            change_pct=change_pct,
            note=note,
            data_quality=data_quality,
        )
        db.add(obs)
        db.commit()

        logger.info(
            f"Written: {self.indicator_name} = {value} {self.unit} "
            f"on {target_date} (change: {change_pct}%)"
        )

        return {
            "success": True,
            "value": value,
            "change_pct": change_pct,
            "date": str(target_date),
        }

    async def safe_collect(self, db=None) -> dict:
        """
        带异常保护的采集入口
        返回统一格式的 dict
        """
        try:
            result = await self.collect(db=db)
            return result
        except Exception as e:
            logger.error(f"Collector {self.source}/{self.indicator_name} failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": self.source,
                "indicator": self.indicator_name,
            }
