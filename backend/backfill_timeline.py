"""
历史数据回采脚本
将过去6个月的 IndicatorObservation 按规则回采到 TimelineEvent。

规则：
- 已知信源确切发布时间 → 创建 TimelineEvent
- 仅知数据日期但不知信源时间 → 跳过
"""

import logging
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)


# 可确定信源时间的指标列表
# 这些指标的 IndicatorObservation.date = 信源发布日期
KNOWN_PUBLICATION_DATES = {
    "tsmc_monthly_revenue",      # TSMC 每月10日发布上月营收
}


def determine_source_time(obs) -> datetime | None:
    """
    判断 IndicatorObservation 的信源发布时间。

    返回 datetime 如果可确定，否则返回 None。
    """
    indicator = obs.indicator
    if not indicator:
        return None

    # 1) TSMC月营收：date 就是发布日期（每月10日）
    if indicator.name in KNOWN_PUBLICATION_DATES:
        if isinstance(obs.date, date):
            return datetime.combine(obs.date, datetime.min.time())
        return None

    # 2) 其他指标的判断规则可扩展：
    # - 如果 note 中包含确切的发布日期信息，可解析
    # - 如果 data_quality 不是 "confirmed" 或来自 fallback，跳过
    if obs.data_quality != "confirmed":
        return None

    # 3) 默认：无法确定，返回 None
    return None


def backfill_6months(db) -> dict:
    """
    回采过去6个月的历史数据到 TimelineEvent。

    Returns:
        {"created": N, "skipped": N, "total": N, "details": [...]}
    """
    from models import IndicatorObservation, KeyIndicator, TimelineEvent

    cutoff = date.today() - timedelta(days=180)

    observations = (
        db.query(IndicatorObservation)
        .join(KeyIndicator, IndicatorObservation.indicator_id == KeyIndicator.id)
        .filter(IndicatorObservation.date >= cutoff)
        .order_by(IndicatorObservation.date.desc())
        .all()
    )

    created = 0
    skipped = 0
    details = []

    for obs in observations:
        # 检查是否已有 TimelineEvent
        existing = (
            db.query(TimelineEvent)
            .filter(TimelineEvent.indicator_observation_id == obs.id)
            .first()
        )
        if existing:
            continue

        source_time = determine_source_time(obs)
        if source_time is None:
            skipped += 1
            details.append({
                "id": obs.id,
                "indicator": obs.indicator.name if obs.indicator else "?",
                "date": str(obs.date),
                "action": "skipped",
                "reason": "无法确定信源发布时间",
            })
            continue

        indicator = obs.indicator
        ticker_map = {
            "tsmc_monthly_revenue": ["TSM"],
            "tsmc_cowos_capacity": ["TSM"],
            "dram_contract_price": ["MU"],
            "nand_contract_price": ["MU"],
            "server_dram_price": ["MU"],
            "enterprise_ssd_price": ["MU"],
            "dram_industry_revenue": ["MU"],
            "hbm_trend": ["MU"],
            "memory_vs_foundry": ["TSM"],
            "global_semiconductor_sales": ["TSM", "NVDA"],
            "semi_equipment_billings": ["ASML", "AMAT"],
            "silicon_wafer_shipments": ["TSM"],
            "asml_backlog": ["ASML"],
            "nvidia_dc_revenue": ["NVDA"],
        }
        tickers = ticker_map.get(indicator.name, []) if indicator else []
        value_display = f"{obs.value}{' ' + indicator.unit if indicator and indicator.unit else ''}"
        if obs.change_pct is not None:
            value_display += f" ({obs.change_pct:+.1f}%)"

        tl = TimelineEvent(
            event_type="collection",
            event_time=source_time,
            title=indicator.name_cn or indicator.name if indicator else "未知指标",
            description=(indicator.description or "") if indicator else "",
            related_tickers=",".join(tickers) if tickers else None,
            related_indicators=indicator.name_cn or indicator.name if indicator else None,
            indicator_observation_id=obs.id,
            source_name=indicator.source if indicator else None,
            indicator_name_cn=indicator.name_cn if indicator else None,
            value_display=value_display,
        )
        db.add(tl)
        created += 1
        details.append({
            "id": obs.id,
            "indicator": indicator.name if indicator else "?",
            "date": str(obs.date),
            "action": "created",
            "source_time": source_time.isoformat(),
        })

    db.commit()

    # 为所有新创建的 TimelineEvent 计算涨跌幅
    for detail in details:
        if detail["action"] == "created":
            try:
                tl = (
                    db.query(TimelineEvent)
                    .filter(TimelineEvent.indicator_observation_id == detail["id"])
                    .first()
                )
                if tl and tl.related_tickers:
                    from price_performance import update_timeline_returns
                    update_timeline_returns(db, tl)
            except Exception as e:
                logger.warning(f"Failed to compute returns for observation {detail['id']}: {e}")

    return {
        "created": created,
        "skipped": skipped,
        "total": len(observations),
        "details": details,
    }


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    from database import SessionLocal
    db = SessionLocal()
    try:
        result = backfill_6months(db)
        print(f"=== 回采完成 ===")
        print(f"总计: {result['total']} 条观测")
        print(f"创建: {result['created']} 条时间线事件")
        print(f"跳过: {result['skipped']} 条 (无法确定信源时间)")

        if result["details"]:
            print(f"\n明细:")
            for d in result["details"]:
                if d["action"] == "created":
                    print(f"  ✅ {d['indicator']} ({d['date']}) → 信源时间 {d['source_time']}")
                else:
                    print(f"  ⏭️  {d['indicator']} ({d['date']}) — {d['reason']}")
    finally:
        db.close()
