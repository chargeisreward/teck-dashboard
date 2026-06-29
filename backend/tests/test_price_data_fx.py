"""测试 price_data._to_usd_b：yfinance FX 转换的 helper。

设计动机：
  yfinance.info["marketCap"] / ["totalRevenue"] 对 ADR/海外 ticker 返回公司本地币种
  （JPY/KRW/TWD/EUR 等）。直接 /1e8 会显示成错误的 USD billion（ATEYY 营收曾被显示成 ¥11,286 亿）。
  _to_usd_b 应该按 yfinance 返回的 currency 字段从 fx_rate_cache 取汇率换算。
"""
from datetime import date

import pytest

from models import FxRateCache
from price_data import _to_usd_b, _currency_from_yfinance_info


def test_usd_passthrough():
    """USD 直接 /1e8，不查 FX。"""
    # 1 trillion USD = 10000 亿 USD
    assert _to_usd_b(1_000_000_000_000, "USD") == 10000.0
    # Apple-like: market_cap ~$3.5T → 35000 亿 USD
    assert _to_usd_b(3_500_000_000_000, "USD") == 35000.0


def test_none_input_returns_none():
    assert _to_usd_b(None, "USD") is None
    assert _to_usd_b(None, "JPY") is None


def test_no_db_session_returns_none_for_non_usd():
    """非 USD 但没有 db session（无法查汇率）→ 返回 None，宁缺勿错。"""
    assert _to_usd_b(1_000_000_000_000, "JPY", db=None) is None


def test_jpy_uses_fx_cache(db):
    """JPY 用 fx_rate_cache 里的汇率转 USD。"""
    # 1 USD = 150 JPY；145,499,096,000 JPY → $969,993,973 USD → 9.7 亿 USD
    db.add(FxRateCache(
        base_currency="JPY", quote_currency="USD",
        rate=150.0, date=date.today(),
    ))
    db.commit()

    # Advantest market_cap 实际 ~¥145 trillion ≈ $966B；测试用 ¥145,499,096,000 (~$970M)
    result = _to_usd_b(145_499_096_000, "JPY", db=db)
    # 145499096000 / 150 = 969,993,973 USD / 1e8 = 9.70 亿 USD
    assert result == pytest.approx(9.70, abs=0.01)


def test_eur_uses_fx_cache(db):
    """EUR 同样按 FX 转换。"""
    db.add(FxRateCache(
        base_currency="EUR", quote_currency="USD",
        rate=1.1, date=date.today(),
    ))
    db.commit()
    # €110B → $100B → 1000 亿 USD
    result = _to_usd_b(110_000_000_000, "EUR", db=db)
    assert result == pytest.approx(1000.0, abs=0.01)


def test_missing_fx_returns_none(db):
    """fx_rate_cache 没数据且 CDN 不可达 → 返回 None。"""
    # 直接传 currency='XYZ'（未知币种），无缓存；不会联网
    result = _to_usd_b(1000, "XYZ", db=db)
    assert result is None


def test_currency_from_yfinance_info_prefers_financial_currency():
    """info["financialCurrency"] 优先（报表币种）于 info["currency"]（市值币种）。"""
    info = {"financialCurrency": "JPY", "currency": "USD"}
    assert _currency_from_yfinance_info(info) == "JPY"


def test_currency_from_yfinance_info_falls_back_to_currency():
    info = {"currency": "KRW"}
    assert _currency_from_yfinance_info(info) == "KRW"


def test_currency_from_yfinance_info_empty():
    assert _currency_from_yfinance_info({}) == "USD"
    assert _currency_from_yfinance_info(None) == "USD"


def test_ateyy_revenue_bug_regression(db):
    """回归测试：原 bug 是 ATEYY totalRevenue (JPY) 被直接 /1e8 写出 11286.1。

    修复后：raw ¥1,128,610,004,992 ÷ FX_rate 149.258 → $7,560,xxx,xxx → 75.6 亿 USD
    （Advantest FY2025 实际约 ¥779B ≈ $5.2B 的 TTM 营收量级，远小于错误值 11,286 亿）
    """
    db.add(FxRateCache(
        base_currency="JPY", quote_currency="USD",
        rate=149.25801135, date=date.today(),
    ))
    db.commit()

    # yfinance 当前为 ATEYY 返回的 totalRevenue 原始值
    raw_jpy = 1_128_610_004_992
    result = _to_usd_b(raw_jpy, "JPY", db=db)

    # 关键断言：结果绝对不应大于 1000（避免再回到 11,286 这种 200x 错误）
    assert result is not None
    assert result < 1000, f"FX 转换后仍异常大：{result}，可能 yfinance 字段变了"
    # 期望 ~75.6 亿 USD
    assert result == pytest.approx(75.61, abs=0.1)


def test_helpers_compose_cleanly(db):
    """组合：info dict → currency → _to_usd_b。"""
    db.add(FxRateCache(
        base_currency="TWD", quote_currency="USD",
        rate=32.0, date=date.today(),
    ))
    db.commit()

    info = {"financialCurrency": "TWD", "totalRevenue": 1_600_000_000_000}
    cur = _currency_from_yfinance_info(info)
    result = _to_usd_b(info["totalRevenue"], cur, db=db)
    # 1.6T TWD / 32 = 50B USD / 1e8 = 500 亿 USD
    assert result == pytest.approx(500.0, abs=0.01)