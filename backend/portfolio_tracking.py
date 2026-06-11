"""
组合跟踪核心计算模块
计算每个持仓的期间涨跌幅、EPS、前瞻PE、组合级加权指标
"""
import logging
from bisect import bisect_right
from datetime import date, timedelta
from typing import Optional

from models import PriceCache, Financial, Forecast, Company

logger = logging.getLogger(__name__)


def compute_holding_returns(db, ticker: str) -> dict:
    """
    从 price_cache 计算股票多期间涨跌幅。

    Returns:
        {"return_1d": float, "return_1w": float, ..., "return_3y": float}
        缺数据返回 {}
    """
    rows = (
        db.query(PriceCache)
        .filter(PriceCache.ticker == ticker.upper())
        .order_by(PriceCache.date)
        .all()
    )
    if len(rows) < 2:
        return {}

    dates = [r.date for r in rows]
    prices = [r.price for r in rows]
    latest_price = prices[-1]
    today = dates[-1]

    periods = [
        ("return_1d", 1), ("return_1w", 7), ("return_1m", 30),
        ("return_3m", 90), ("return_6m", 180), ("return_1y", 365),
        ("return_3y", 1095),
    ]

    results = {}
    for key, days in periods:
        if key == "return_1d" and len(prices) >= 2:
            prev_price = prices[-2]
            results[key] = round((latest_price - prev_price) / prev_price * 100, 2)
        else:
            target = today - timedelta(days=days)
            idx = bisect_right(dates, target) - 1
            if idx >= 0 and idx < len(prices):
                past_price = prices[idx]
                results[key] = round((latest_price - past_price) / past_price * 100, 2)
            else:
                results[key] = None

    return results


def derive_eps_metrics(company_id: int, ticker: str, cache_data: dict, db) -> dict:
    """
    从 stock_info_cache 和 financials 推导 EPS 和前瞻 PE。

    增速 = EPS_TTM / EPS_2025 - 1（基于实际数据）
    前瞻 EPS 采用时间加权复利，考虑当前时间距离 2026/2027 年底的剩余月份。

    Returns:
        {
            "eps_ttm": float | None,          # current_price / pe_ttm
            "eps_2025": float | None,          # 从 FY2025 financials 推导
            "growth_rate": float,              # 基于 EPS_TTM/EPS_2025 的实际增速
            "eps_2026e": float | None,
            "eps_2027e": float | None,
            "forward_pe_2026e": float | None,
            "forward_pe_2027e": float | None,
        }
    """
    current_price = cache_data.get("current_price")
    pe_ttm = cache_data.get("pe_ttm")
    market_cap_b = cache_data.get("market_cap_b")  # 亿(100M)为单位

    # EPS_TTM = price / PE_TTM
    eps_ttm = None
    if current_price and pe_ttm and pe_ttm > 0:
        eps_ttm = round(current_price / pe_ttm, 4)

    # FY2025 EPS = net_income * current_price / market_cap_b
    # financials.net_income 和 market_cap_b 均以 亿(100M) 为单位
    eps_2025 = None
    financial = (
        db.query(Financial)
        .filter(Financial.company_id == company_id, Financial.fiscal_year == 2025)
        .first()
    )
    if financial and financial.net_income and current_price and market_cap_b and market_cap_b > 0:
        eps_2025 = round(financial.net_income * current_price / market_cap_b, 4)

    # ── 增速 = EPS_TTM / EPS_2025 - 1 ──
    growth_rate = 15.0  # 默认
    if eps_ttm and eps_ttm > 0 and eps_2025 and eps_2025 > 0:
        raw_g = (eps_ttm / eps_2025) - 1
        growth_rate = round(raw_g * 100, 1)  # 转为百分比
    else:
        # 无 EPS_2025 时尝试从 Forecasts 表读取
        forecast = (
            db.query(Forecast)
            .filter(Forecast.company_id == company_id, Forecast.target_year == 2026)
            .first()
        )
        if forecast and forecast.revenue_growth_est:
            growth_rate = forecast.revenue_growth_est

    # ── 时间加权前瞻 EPS ──
    # 当前时间 2026-06-11，计算距各年底的剩余年数
    today = date(2026, 6, 11)
    end_2026 = date(2026, 12, 31)
    end_2027 = date(2027, 12, 31)
    years_to_2026 = (end_2026 - today).days / 365.0   # ≈0.556
    years_to_2027 = (end_2027 - today).days / 365.0   # ≈1.556

    eps_2026e = None
    eps_2027e = None
    forward_pe_2026e = None
    forward_pe_2027e = None

    if eps_ttm is not None and eps_ttm > 0:
        g_dec = growth_rate / 100.0  # 转为小数
        eps_2026e = round(eps_ttm * ((1 + g_dec) ** years_to_2026), 4)
        eps_2027e = round(eps_ttm * ((1 + g_dec) ** years_to_2027), 4)

        if current_price:
            forward_pe_2026e = round(current_price / eps_2026e, 2) if eps_2026e else None
            forward_pe_2027e = round(current_price / eps_2027e, 2) if eps_2027e else None
    elif eps_2025 is not None and eps_2025 > 0:
        # 没有 TTM 时退一步使用 EPS_2025
        g_dec = growth_rate / 100.0
        eps_2026e = round(eps_2025 * ((1 + g_dec) ** years_to_2026), 4)
        eps_2027e = round(eps_2025 * ((1 + g_dec) ** years_to_2027), 4)

        if current_price:
            forward_pe_2026e = round(current_price / eps_2026e, 2) if eps_2026e else None
            forward_pe_2027e = round(current_price / eps_2027e, 2) if eps_2027e else None

    return {
        "eps_ttm": eps_ttm,
        "eps_2025": eps_2025,
        "growth_rate": growth_rate,
        "eps_2026e": eps_2026e,
        "eps_2027e": eps_2027e,
        "forward_pe_2026e": forward_pe_2026e,
        "forward_pe_2027e": forward_pe_2027e,
    }


def compute_portfolio_aggregates(holdings_data: list[dict]) -> dict:
    """
    计算组合级加权指标，含现金计算。

    holdings_data: [...holding_dict...] 含 weight, pe_ttm, eps_ttm, return_* 等字段

    Returns:
        {
            "total_weight": float,      # 持仓权重和
            "cash_weight": float,       # 100 - total (可负)
            "weighted_pe": float | None,
            "weighted_eps_ttm": float | None,
            "weighted_eps_2026e": float | None,
            "weighted_eps_2027e": float | None,
            "weighted_return_1d": float | None,
            ...
        }
    """
    total_weight = sum(h.get("weight", 0) for h in holdings_data)
    cash_weight = round(100.0 - total_weight, 1)

    def weighted_avg(attr):
        num = sum(h.get("weight", 0) * h.get(attr) for h in holdings_data if h.get(attr) is not None)
        den = sum(h.get("weight", 0) for h in holdings_data if h.get(attr) is not None)
        return round(num / den, 2) if den > 0 else None

    result = {
        "total_weight": round(total_weight, 1),
        "cash_weight": cash_weight,
        "weighted_pe": weighted_avg("pe_ttm"),
        "weighted_eps_ttm": weighted_avg("eps_ttm"),
        "weighted_eps_2026e": weighted_avg("eps_2026e"),
        "weighted_eps_2027e": weighted_avg("eps_2027e"),
        "weighted_forward_pe_2026e": weighted_avg("forward_pe_2026e"),
        "weighted_forward_pe_2027e": weighted_avg("forward_pe_2027e"),
    }

    for period in ["return_1d", "return_1w", "return_1m", "return_3m",
                    "return_6m", "return_1y", "return_3y"]:
        result[f"weighted_{period}"] = weighted_avg(period)

    return result
