"""
价格涨跌幅计算模块
计算时间线事件前后10个交易日的绝对/相对(对标SOX)涨跌幅
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from price_data import get_price_history_cached

logger = logging.getLogger(__name__)

SOX_TICKER = "SOX"


def _find_price_on_date(data: list[dict], target_date) -> Optional[float]:
    """从价格历史中找到最接近目标日期的收盘价"""
    from datetime import date as date_type

    if isinstance(target_date, datetime):
        target_date = target_date.date()
    elif isinstance(target_date, str):
        from datetime import datetime as dt
        target_date = dt.strptime(target_date, "%Y-%m-%d").date()

    # 先找精确匹配
    for d in data:
        d_date = d.get("date", "")
        try:
            if len(d_date) >= 10:
                dd = datetime.strptime(d_date[:10], "%Y-%m-%d").date()
                if dd == target_date:
                    return d.get("price")
        except (ValueError, IndexError):
            continue

    # 没有精确匹配，找最接近的（不超过2个交易日）
    best = None
    best_diff = 999
    for d in data:
        d_date = d.get("date", "")
        try:
            if len(d_date) >= 10:
                dd = datetime.strptime(d_date[:10], "%Y-%m-%d").date()
                diff = abs((dd - target_date).days)
                if diff < best_diff and diff <= 3:
                    best_diff = diff
                    best = d.get("price")
        except (ValueError, IndexError):
            continue

    return best


def _get_window_return(data: list[dict], start_dt, end_dt) -> Optional[float]:
    """
    计算 [start_dt, end_dt] 区间的涨跌幅
    返回百分比 (e.g. 5.2 表示 +5.2%)
    """
    start_price = _find_price_on_date(data, start_dt)
    end_price = _find_price_on_date(data, end_dt)

    if start_price is None or end_price is None or start_price == 0:
        return None

    pct = (end_price - start_price) / start_price * 100
    # 防止 NaN/Inf 渗入 JSON(标准 JSON 不允许这两种值)
    if pct != pct or pct in (float('inf'), float('-inf')):
        return None
    return round(pct, 2)


def compute_relative_performance(
    tickers: list[str],
    event_date: datetime,
    db,
    days: int = 10,
) -> dict:
    """
    计算多个 ticker 在事件前后 days 个交易日的涨跌幅及相对 SOX 的表现。

    Args:
        tickers: 相关股票 ticker 列表
        event_date: 事件发生时间
        db: 数据库 session
        days: 交易日窗口 (默认10)

    Returns:
        {
            "pre": {
                "NVDA": {"abs": 5.2, "rel": 2.1},
                "SOX": {"abs": 3.1},
            },
            "post": {
                "NVDA": {"abs": -1.5, "rel": 0.5},
                "SOX": {"abs": -2.0},
            },
        }
    """
    pre_start = event_date - timedelta(days=days + 1)
    pre_end = event_date - timedelta(days=1)
    post_start = event_date + timedelta(days=1)
    post_end = event_date + timedelta(days=days)

    fetch_days = days + 5
    result = {"pre": {}, "post": {}}

    # 先获取 SOX 数据
    sox_data = get_price_history_cached(SOX_TICKER, fetch_days * 2, db)
    if sox_data:
        sox_pre = _get_window_return(sox_data, pre_start, pre_end)
        sox_post = _get_window_return(sox_data, post_start, post_end)
        result["pre"]["SOX"] = {"abs": sox_pre}
        result["post"]["SOX"] = {"abs": sox_post}

    # 获取每个 ticker 的数据
    for ticker in tickers:
        ticker = ticker.strip().upper()
        if not ticker:
            continue

        data = get_price_history_cached(ticker, fetch_days * 2, db)
        if not data:
            logger.info(f"No price data for {ticker}, skipping")
            continue

        pre_abs = _get_window_return(data, pre_start, pre_end)
        post_abs = _get_window_return(data, post_start, post_end)

        entry = {"abs": pre_abs}
        if pre_abs is not None and sox_data:
            sox_val = result["pre"].get("SOX", {}).get("abs")
            if sox_val is not None:
                rel = pre_abs - sox_val
                if rel == rel and rel not in (float('inf'), float('-inf')):
                    entry["rel"] = round(rel, 2)

        result["pre"][ticker] = entry

        post_entry = {"abs": post_abs}
        if post_abs is not None and sox_data:
            sox_val = result["post"].get("SOX", {}).get("abs")
            if sox_val is not None:
                rel = post_abs - sox_val
                if rel == rel and rel not in (float('inf'), float('-inf')):
                    post_entry["rel"] = round(rel, 2)

        result["post"][ticker] = post_entry

    return result


def update_timeline_returns(db, timeline_event) -> None:
    """
    计算并更新 TimelineEvent 的涨跌幅数据。
    同步更新 pre_event_returns (事件前)；
    如果事件已超过10天，同时更新 post_event_returns。
    """
    if not timeline_event.related_tickers:
        return

    tickers = [t.strip() for t in timeline_event.related_tickers.split(",") if t.strip()]

    event_date = timeline_event.event_time
    if isinstance(event_date, str):
        from datetime import datetime as dt
        event_date = dt.fromisoformat(event_date)

    result = compute_relative_performance(tickers, event_date, db)

    timeline_event.pre_event_returns = result.get("pre")

    now = datetime.now()
    if now >= event_date + timedelta(days=10):
        timeline_event.post_event_returns = result.get("post")
        timeline_event.post_event_updated = True

    db.commit()


def refresh_pending_post_events(db) -> int:
    """
    刷新所有待更新的 post_event_returns (事件已过10天但未更新)
    返回更新的条目数
    """
    from models import TimelineEvent

    now = datetime.now()
    cutoff = now - timedelta(days=10)

    pending = (
        db.query(TimelineEvent)
        .filter(
            TimelineEvent.post_event_updated == False,
            TimelineEvent.event_time <= cutoff,
            TimelineEvent.related_tickers.isnot(None),
            TimelineEvent.related_tickers != "",
        )
        .all()
    )

    updated = 0
    for event in pending:
        try:
            update_timeline_returns(db, event)
            updated += 1
        except Exception as e:
            logger.error(f"Failed to update returns for event {event.id}: {e}")

    return updated
