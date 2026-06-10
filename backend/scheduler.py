"""
定时调度器
- 每日 6:00 / 14:00 / 22:00 自动采集全部数据源
- 每4小时刷新待更新的事件后涨跌幅
"""

import logging
import asyncio
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def auto_collect_and_timeline():
    """自动采集全部数据源，同步创建 TimelineEvent"""
    try:
        from database import SessionLocal
        from industry_collector import collect_all

        db = SessionLocal()
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(collect_all(db=db))
            loop.close()

            # 为每个成功采集创建 TimelineEvent (复用 main.py 的逻辑)
            from models import KeyIndicator, IndicatorObservation, TimelineEvent
            from price_performance import update_timeline_returns

            for r in results.get("success", []):
                try:
                    indicator_name = r.get("indicator", "")
                    ind = db.query(KeyIndicator).filter(
                        KeyIndicator.name == indicator_name
                    ).first()
                    if not ind:
                        continue

                    obs = (
                        db.query(IndicatorObservation)
                        .filter(IndicatorObservation.indicator_id == ind.id)
                        .order_by(IndicatorObservation.date.desc())
                        .first()
                    )
                    if not obs:
                        continue

                    existing_tl = db.query(TimelineEvent).filter(
                        TimelineEvent.indicator_observation_id == obs.id
                    ).first()
                    if existing_tl:
                        continue

                    # 从共享模块读取 ticker 映射
                    from indicator_map import INDICATOR_TICKER_MAP

                    tickers = INDICATOR_TICKER_MAP.get(ind.name, [])
                    value_display = f"{obs.value}{' ' + ind.unit if ind.unit else ''}"
                    if obs.change_pct is not None:
                        value_display += f" ({obs.change_pct:+.1f}%)"

                    tl = TimelineEvent(
                        event_type="collection",
                        event_time=datetime.now(),
                        title=ind.name_cn or ind.name,
                        description=ind.description or "",
                        related_tickers=",".join(tickers) if tickers else None,
                        related_indicators=ind.name_cn or ind.name,
                        indicator_observation_id=obs.id,
                        source_name=ind.source,
                        indicator_name_cn=ind.name_cn,
                        value_display=value_display,
                    )
                    db.add(tl)
                    db.commit()
                    db.refresh(tl)

                    if tl.related_tickers:
                        try:
                            update_timeline_returns(db, tl)
                        except Exception as e:
                            logger.warning(f"Returns failed for {indicator_name}: {e}")
                except Exception as e:
                    logger.warning(f"Timeline event creation failed: {e}")

            logger.info(f"Auto-collect: {len(results.get('success', []))} success, {len(results.get('errors', []))} errors")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Auto-collect failed: {e}")


def refresh_post_event_returns():
    """刷新所有待更新的事件后涨跌幅"""
    try:
        from database import SessionLocal
        from price_performance import refresh_pending_post_events

        db = SessionLocal()
        try:
            updated = refresh_pending_post_events(db)
            if updated:
                logger.info(f"Refreshed post-event returns for {updated} events")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Refresh post-event returns failed: {e}")


def refresh_company_financials():
    """刷新所有链上公司的股价/PE/市值数据"""
    try:
        from database import SessionLocal
        from refresh_company_data import refresh_all_company_data

        db = SessionLocal()
        try:
            results = refresh_all_company_data(db)
            updated = results.get("updated", 0)
            errors = results.get("errors", 0)
            if updated or errors:
                logger.info(f"Company data refresh: {updated} updated, {errors} errors")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Company data refresh failed: {e}")


def init_scheduler():
    """初始化定时调度器"""
    # 每日 6:00, 14:00, 22:00 自动采集
    scheduler.add_job(
        auto_collect_and_timeline,
        trigger="cron",
        hour="6,14,22",
        minute=0,
        id="industry_collect",
        name="Auto collect industry data",
        replace_existing=True,
    )

    # 每日 7:00 / 19:00 刷新公司股价/PE/市值
    scheduler.add_job(
        refresh_company_financials,
        trigger="cron",
        hour="7,19",
        minute=0,
        id="refresh_company_data",
        name="Refresh company stock data",
        replace_existing=True,
    )

    # 每4小时刷新待更新的事件后涨跌幅
    scheduler.add_job(
        refresh_post_event_returns,
        trigger="interval",
        hours=4,
        id="refresh_post_returns",
        name="Refresh post-event returns",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started: auto-collect at 6/14/22, refresh company data at 7/19, refresh returns every 4h")
