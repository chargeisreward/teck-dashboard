"""
定时调度器
- 每日 6:00 / 18:00 自动采集产业数据 + MiniMax AI分析
- 每15分钟刷新关注公司实时价格
- 每日 7:00 / 19:00 刷新公司股价/PE/市值
- 每4小时刷新待更新的事件后涨跌幅
"""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def auto_collect_and_analyze():
    """自动采集全部数据源 + MiniMax AI分析"""
    try:
        from database import SessionLocal
        from industry_collector import collect_all

        db = SessionLocal()
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(collect_all(db=db))
            loop.close()

            from models import KeyIndicator, IndicatorObservation, TimelineEvent
            from price_performance import update_timeline_returns

            collected = 0
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

                    # 检查是否已存在对应的 TimelineEvent
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
                    collected += 1

                    if tl.related_tickers:
                        try:
                            update_timeline_returns(db, tl)
                        except Exception as e:
                            logger.warning(f"Returns failed for {indicator_name}: {e}")
                except Exception as e:
                    logger.warning(f"Timeline event creation failed: {e}")

            logger.info(f"Auto-collect: {collected} new events from {len(results.get('success', []))} indicators")

            # ── MiniMax AI 批量分析 ──
            try:
                from main import batch_analyze_industry_impact
                analyzed = batch_analyze_industry_impact(db)
                if analyzed:
                    logger.info(f"MiniMax analysis generated for {analyzed} indicators")
            except Exception as e:
                logger.warning(f"Batch analyze failed: {e}")

        finally:
            db.close()
    except Exception as e:
        logger.error(f"Auto-collect failed: {e}")


def refresh_company_financials():
    """刷新所有链上公司的股价/PE/市值数据 + 增量价格补缺口 + 同步 MarketData"""
    try:
        from database import SessionLocal
        from refresh_company_data import refresh_all_company_data
        from backfill_market_data import backfill_market_data
        from backfill_3y_prices import incremental_backfill_prices

        db = SessionLocal()
        try:
            results = refresh_all_company_data(db)
            updated = results.get("updated", 0)
            errors = results.get("errors", 0)
            if updated or errors:
                logger.info(f"Company data refresh: {updated} updated, {errors} errors")
        finally:
            db.close()

        # ── 增量价格补缺口(只追加,不覆盖) ──
        # 设计动机: 数据 API 可能限流, 首次 bulk 失败时缺口靠调度逐步补足
        try:
            inc_result = incremental_backfill_prices()
            logger.info(f"Incremental price backfill: {inc_result}")
        except Exception as e:
            logger.warning(f"Incremental backfill failed: {e}")

        backfill_market_data()
    except Exception as e:
        logger.error(f"Company data refresh failed: {e}")


def refresh_follow_prices_15min():
    """每15分钟刷新关注股票的实时价格"""
    try:
        from database import SessionLocal
        from models import Follow, Company, StockInfoCache
        from price_data import get_stock_info
        from datetime import date

        db = SessionLocal()
        try:
            follows = db.query(Follow).all()
            if not follows:
                return

            company_ids = [f.company_id for f in follows]
            companies = {
                c.id: c
                for c in db.query(Company).filter(Company.id.in_(company_ids)).all()
            }

            updated = 0
            errors = 0
            for f in follows:
                co = companies.get(f.company_id)
                if not co or not co.ticker:
                    continue
                try:
                    live = get_stock_info(co.ticker)
                    if live and live.get("source"):
                        ticker_upper = co.ticker.upper()
                        existing = db.query(StockInfoCache).filter(
                            StockInfoCache.ticker == ticker_upper
                        ).first()
                        if existing:
                            existing.data_json = live
                            existing.updated_at = date.today()
                        else:
                            db.add(StockInfoCache(
                                ticker=ticker_upper,
                                data_json=live,
                                updated_at=date.today(),
                            ))
                        updated += 1
                except Exception as e:
                    logger.warning(f"Price refresh failed for {co.ticker}: {e}")
                    errors += 1

            db.commit()
            if updated:
                logger.info(f"15min price refresh: {updated} updated, {errors} errors")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"15min price refresh failed: {e}")


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


def init_scheduler():
    """初始化定时调度器"""
    # ── 每日 6:00, 18:00 自动采集 + MiniMax分析 ──
    scheduler.add_job(
        auto_collect_and_analyze,
        trigger="cron",
        hour="6,18",
        minute=0,
        id="industry_collect",
        name="Auto collect + analyze industry data",
        replace_existing=True,
    )

    # ── 每15分钟刷新关注公司实时价格 ──
    scheduler.add_job(
        refresh_follow_prices_15min,
        trigger="interval",
        minutes=15,
        id="refresh_prices_15min",
        name="Refresh follow prices every 15 min",
        replace_existing=True,
    )

    # ── 每日 7:00 / 19:00 刷新公司股价/PE/市值 ──
    scheduler.add_job(
        refresh_company_financials,
        trigger="cron",
        hour="7,19",
        minute=0,
        id="refresh_company_data",
        name="Refresh company stock data",
        replace_existing=True,
    )

    # ── 每4小时刷新待更新的事件后涨跌幅 ──
    scheduler.add_job(
        refresh_post_event_returns,
        trigger="interval",
        hours=4,
        id="refresh_post_returns",
        name="Refresh post-event returns",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started: auto-collect at 6/18, price refresh every 15min, "
        "company data at 7/19, post-returns every 4h"
    )
