"""
价格数据获取模块
数据源优先级:
  1. 腾讯财经 API (免费, 美股/港股/A股)
  2. yfinance (美股/港股/全球)
  3. akshare (A股/A股实时行情)
  4. 缓存数据（fallback）

Tencent API:
  - 实时行情: https://qt.gtimg.cn/q=usTSM.N,usEWY.AM
  - 历史K线: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=usTSM.N,day,start,end,2000,qfq
"""
import logging
import json
import urllib.request
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── yfinance ────────────────────────────────────────────────────
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False
    logger.warning("yfinance not installed; US/global price data will be limited")

# ── AKShare (A股) ──────────────────────────────────────────────
try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False
    logger.warning("akshare not installed; A-share data unavailable")

# ── Ticker 映射 ────────────────────────────────────────────────
# 将公司名称/已知 ticker 映射到不同数据源对应的代码
A_SHARE_MAP = {
    # 晶圆代工
    "SMIC": "688981",          # 中芯国际 A股
    "SMI": "688981",
    # 封装测试
    "JCET": "600584",          # 长电科技
    # EDA
    "Siemens EDA": "600000",   # 西门子 EDA 无直接A股，placeholder
}

# 港股通/香港 ticker 映射 (akshare 使用 hk_前缀)
HK_TICKER_MAP = {
    "TCEHY": "hk_00700",       # 腾讯控股 (美股ADR -> 港股)
    "BABA": "hk_09988",        # 阿里巴巴 (美股ADR -> 港股)
    "BIDU": "hk_09888",        # 百度 (美股ADR -> 港股)
    "XIACF": "hk_01810",       # 小米 (美股OTC -> 港股)
    "MPNGY": "hk_03690",       # 美团 (美股ADR -> 港股)
    "PDD": "hk_PDD",           # 拼多多无港股
}

# 中国公司 yfinance 不一定有数据的 ticker 映射到港股/A股
CN_TICKER_MAP = {
    "SMI": "688981.SH",        # SMIC A股 (588981.SH)
}

# ── 腾讯财经 API (US 股票) ───────────────────────────────────────
# 格式: us{代码} (不包含交易所后缀, 单个查询时不需要)
# 历史K线需要完整格式: us{代码}.{交易所}  交易所: N=NYSE, OQ=NASDAQ, AM=NYSE Arca
TENCENT_US_MAP = {
    "TSM": "usTSM",            # 台积电 ADR
    "EWY": "usEWY",            # iShares MSCI South Korea ETF
    "AIA": "usAIA",            # iShares Asia 50 ETF
    "NVDA": "usNVDA",          # NVIDIA
    "ASML": "usASML",          # ASML
    "AVGO": "usAVGO",          # Broadcom
    "MU": "usMU",              # Micron
    "AMD": "usAMD",            # AMD
    "INTC": "usINTC",          # Intel
    "AAPL": "usAAPL",          # Apple
    "MSFT": "usMSFT",          # Microsoft
    "GOOGL": "usGOOGL",        # Google
    "META": "usMETA",          # Meta
    "AMZN": "usAMZN",          # Amazon
    "SOX": "usSOX",            # 费城半导体指数
    # 补充 US ticker
    "AMAT": "usAMAT",          # Applied Materials
    "AMKR": "usAMKR",          # Amkor
    "ANET": "usANET",          # Arista
    "ANSS": "usANSS",          # Ansys
    "ARM": "usARM",            # ARM Holdings
    "ASMIY": "usASMIY",        # ASM International (OTC)
    "ATEYY": "usATEYY",        # Advantest (OTC)
    "CDNS": "usCDNS",          # Cadence
    "CSCO": "usCSCO",          # Cisco
    "GFS": "usGFS",            # GlobalFoundries
    "KLAC": "usKLAC",          # KLA Corp
    "LRCX": "usLRCX",          # Lam Research
    "MRVL": "usMRVL",          # Marvell
    "ORCL": "usORCL",          # Oracle
    "QCOM": "usQCOM",          # Qualcomm
    "SIEGY": "usSIEGY",        # Siemens (OTC)
    "SNPS": "usSNPS",          # Synopsys
    "TOELY": "usTOELY",        # Tokyo Electron (OTC)
    "UMC": "usUMC",            # UMC ADR
    "WDC": "usWDC",            # Western Digital
    # ADR / 中国公司 US 上市
    "TCEHY": "usTCEHY",        # 腾讯 ADR
    "BABA": "usBABA",          # 阿里巴巴
    "BIDU": "usBIDU",          # 百度
    "TSLA": "usTSLA",          # 特斯拉
    "XIACF": "usXIACF",        # 小米 OTC
    "MPNGY": "usMPNGY",        # 美团 OTC
    "PDD": "usPDD",            # 拼多多
    "ASX": "usASX",            # 日月光 ASE
}

# 腾讯 US K线格式需要交易所后缀
TENCENT_KLINE_MAP = {
    "TSM": "usTSM.N",          # 台积电 NYSE
    "EWY": "usEWY.AM",         # EWY NYSE Arca
    "AIA": "usAIA.OQ",         # AIA NASDAQ
    "NVDA": "usNVDA.OQ",       # NVIDIA NASDAQ
    "ASML": "usASML.OQ",       # ASML NASDAQ
    "AVGO": "usAVGO.OQ",       # Broadcom NASDAQ
    "MU": "usMU.OQ",           # Micron NASDAQ
    "AMD": "usAMD.OQ",         # AMD NASDAQ
    "INTC": "usINTC.OQ",       # Intel NASDAQ
    "AAPL": "usAAPL.OQ",       # Apple NASDAQ
    "MSFT": "usMSFT.OQ",       # Microsoft NASDAQ
    "GOOGL": "usGOOGL.OQ",     # Google NASDAQ
    "META": "usMETA.OQ",       # Meta NASDAQ
    "AMZN": "usAMZN.OQ",       # Amazon NASDAQ
    "SOX": "usSOX.AM",         # 费城半导体指数 (NYSE Arca)
    # 补充
    "AMAT": "usAMAT.OQ",       # Applied Materials NASDAQ
    "ANET": "usANET.N",        # Arista NYSE
    "ARM": "usARM.OQ",         # ARM NASDAQ
    "CDNS": "usCDNS.OQ",       # Cadence NASDAQ
    "CSCO": "usCSCO.OQ",       # Cisco NASDAQ
    "GFS": "usGFS.OQ",         # GlobalFoundries NASDAQ
    "KLAC": "usKLAC.OQ",       # KLA NASDAQ
    "LRCX": "usLRCX.OQ",       # Lam Research NASDAQ
    "MRVL": "usMRVL.OQ",       # Marvell NASDAQ
    "ORCL": "usORCL.N",        # Oracle NYSE
    "QCOM": "usQCOM.OQ",       # Qualcomm NASDAQ
    "SNPS": "usSNPS.OQ",       # Synopsys NASDAQ
    "UMC": "usUMC.N",          # UMC NYSE
    "WDC": "usWDC.N",          # Western Digital NYSE
    "TCEHY": "usTCEHY.OQ",     # 腾讯 ADR (OTCQX)
    "BABA": "usBABA.N",        # 阿里巴巴 NYSE
    "BIDU": "usBIDU.OQ",       # 百度 NASDAQ
    "TSLA": "usTSLA.OQ",       # 特斯拉 NASDAQ
    "XIACF": "usXIACF.OQ",     # 小米 OTC
    "MPNGY": "usMPNGY.OQ",     # 美团 OTC
    "PDD": "usPDD.OQ",         # 拼多多 NASDAQ
    "ASX": "usASX.N",          # 日月光 ASE NYSE
}

TENCENT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 特殊 ticker 映射 (yfinance 需要不同的格式)
YFINANCE_TICKER_MAP = {
    "SOX": "^SOX",             # 费城半导体指数
    "000660": "000660.KS",     # SK Hynix (KOSPI)
    "SMSN": "005930.KS",       # Samsung Electronics (KOSPI)
}

# ── Naver API (韩国股票) ──────────────────────────────────────────
NAVER_KOREAN_MAP = {
    "000660": "000660",      # SK Hynix
    "SMSN": "005930",        # Samsung Electronics
}

# 韩元兑美元参考汇率（约值，用于市值换算）
KRW_USD_RATE = 1300.0

# 用于 akshare stock_zh_a_hist 的 adjust 参数
ADJUST_MAP = {"qfq": "前复权", "hfq": "后复权", "": "不复权"}


def _fetch_yfinance(ticker: str, days: int, interval: str) -> list[dict]:
    """通过 yfinance 获取历史价格"""
    if not HAS_YFINANCE:
        return []
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start.strftime("%Y-%m-%d"),
                             end=end.strftime("%Y-%m-%d"),
                             interval=interval)
        if hist.empty:
            return []
        result = []
        prev_close = None
        for idx, row in hist.iterrows():
            d = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
            close = round(float(row.get("Close", 0)), 2)
            change = round((close - prev_close) / prev_close * 100, 2) if prev_close else None
            result.append({
                "date": d,
                "price": close,
                "change_pct": change,
                "volume": int(row.get("Volume", 0)),
                "source": "yfinance",
            })
            prev_close = close
        return result
    except Exception as e:
        logger.warning(f"yfinance fetch failed for {ticker}: {e}")
    return []


def _fetch_akshare_a_share(symbol: str, days: int) -> list[dict]:
    """通过 AKShare 获取 A 股历史行情 (stock_zh_a_hist)"""
    if not HAS_AKSHARE:
        return []
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="qfq",
        )
        if df is None or df.empty:
            return []
        result = []
        prev_close = None
        # akshare 返回的列名: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
        for _, row in df.iterrows():
            d = str(row["日期"])
            close = round(float(row["收盘"]), 2)
            change_pct = row.get("涨跌幅")
            if change_pct is None or pd.isna(change_pct):
                change = round((close - prev_close) / prev_close * 100, 2) if prev_close else None
            else:
                change = round(float(change_pct), 2)
            result.append({
                "date": d,
                "price": close,
                "change_pct": change,
                "volume": int(row.get("成交量", 0)),
                "source": "akshare",
            })
            prev_close = close
        return result
    except Exception as e:
        logger.warning(f"akshare A-share fetch failed for {symbol}: {e}")
    return []


def _fetch_akshare_hk(symbol: str, days: int) -> list[dict]:
    """通过 AKShare 获取港股历史行情 (stock_hk_hist)"""
    if not HAS_AKSHARE:
        return []
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        df = ak.stock_hk_hist(
            symbol=symbol,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="qfq",
        )
        if df is None or df.empty:
            return []
        result = []
        prev_close = None
        for _, row in df.iterrows():
            d = str(row["日期"])
            close = round(float(row["收盘"]), 2)
            change = round(float(row["涨跌幅"]), 2) if "涨跌幅" in row and row["涨跌幅"] else None
            if change is None:
                change = round((close - prev_close) / prev_close * 100, 2) if prev_close else None
            result.append({
                "date": d,
                "price": close,
                "change_pct": change,
                "volume": int(row.get("成交量", 0)),
                "source": "akshare",
            })
            prev_close = close
        return result
    except Exception as e:
        logger.warning(f"akshare HK fetch failed for {symbol}: {e}")
    return []


def _fetch_tencent_kline(ticker: str, days: int) -> list[dict]:
    """通过腾讯财经 API 获取 US 股票历史 K 线数据"""
    tencent_code = TENCENT_KLINE_MAP.get(ticker.upper())
    if not tencent_code:
        return []

    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/"
               f"get?param={tencent_code},day,{start.strftime('%Y-%m-%d')},"
               f"{end.strftime('%Y-%m-%d')},{min(days * 2, 2000)},qfq")
        req = urllib.request.Request(url, headers={"User-Agent": TENCENT_UA})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))

        d = data.get("data", {})
        if not d:
            return []
        key = list(d.keys())[0]
        klines = d[key].get("day", [])
        if not klines:
            return []

        result = []
        prev_close = None
        for k in klines:
            if len(k) < 6:
                continue
            d_str, open_p, close_p, high, low, vol = k[0], k[1], k[2], k[3], k[4], k[5]
            close = round(float(close_p), 2)
            change = round((close - prev_close) / prev_close * 100, 2) if prev_close else None
            result.append({
                "date": d_str,
                "price": close,
                "change_pct": change,
                "volume": int(float(vol)) if vol else 0,
                "source": "tencent",
            })
            prev_close = close
        return result
    except Exception as e:
        logger.warning(f"tencent kline fetch failed for {ticker}: {e}")
    return []


def _fetch_naver_korean_info(ticker: str) -> Optional[dict]:
    """
    通过 Naver Mobile API 获取韩国股票信息（PER, 市值, 价格等）
    支持: KOSPI 股票 (如 000660=SK Hynix, 005930=Samsung)
    """
    import urllib.request
    import json
    import re

    kr_code = NAVER_KOREAN_MAP.get(ticker.upper(), ticker)
    url = f"https://m.stock.naver.com/api/stock/{kr_code}/integration"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": TENCENT_UA})
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read()
        # API 返回 UTF-8 JSON
        data = json.loads(raw.decode("utf-8"))

        if not data or not data.get("totalInfos"):
            logger.warning(f"Naver API returned no data for {ticker}")
            return None

        infos = {item["code"]: item for item in data["totalInfos"]}

        # ── 提取 PER ──
        per_str = infos.get("per", {}).get("value", "0")
        per_match = re.search(r"([\d.]+)", per_str)
        pe_ttm = float(per_match.group(1)) if per_match else None

        # ── 提取 EPS ──
        eps_str = infos.get("eps", {}).get("value", "0")
        eps_match = re.search(r"([\d,]+)", eps_str)
        eps = float(eps_match.group(1).replace(",", "")) if eps_match else None

        # ── 提取收盘价（前日）─
        close_str = infos.get("lastClosePrice", {}).get("value", "0")
        close_val = float(close_str.replace(",", "")) if close_str else None

        # ── 提取当前交易数据（最新行情）─
        deals = data.get("dealTrendInfos", [])
        current_price = None
        change_pct = None
        if deals:
            latest = deals[0]
            cp = latest.get("closePrice", "0")
            current_price = float(cp.replace(",", "")) if cp else None
            # compareToPreviousClosePrice: signed string like "-19,500"
            prev_close_diff = latest.get("compareToPreviousClosePrice", "0")
            prev_close_val = close_val or current_price
            if prev_close_val and current_price:
                change_pct = round((current_price - prev_close_val) / prev_close_val * 100, 2)

        # ── 提取市值 ──
        # Naver 返回格式如 "1,768조 4,993억"（조=万亿, 억=亿）
        market_cap_krw = None
        market_cap_text = infos.get("marketValue", {}).get("value", "")
        if market_cap_text and market_cap_text != "-":
            try:
                import re
                parts = market_cap_text.replace(",", "").split()
                total_krw = 0.0
                for p in parts:
                    if "조" in p:
                        num = float(p.replace("조", ""))
                        total_krw += num * 1_000_000_000_000  # 1조 = 10^12
                    elif "억" in p:
                        num = float(p.replace("억", ""))
                        total_krw += num * 100_000_000  # 1억 = 10^8
                if total_krw > 0:
                    market_cap_krw = total_krw
            except (ValueError, AttributeError) as e:
                logger.warning(f"Failed to parse Korean market cap '{market_cap_text}': {e}")

        # 如果 totalInfos 解析失败，尝试从 industryCompareInfo 获取数值（单位：百万韩元）
        if market_cap_krw is None:
            comp_info = data.get("industryCompareInfo", [])
            for ci in comp_info:
                if ci.get("itemCode") == kr_code:
                    mcap_val = ci.get("marketValue", "0")
                    if mcap_val and mcap_val != "-":
                        try:
                            market_cap_krw = float(mcap_val.replace(",", "")) * 1_000_000  # 백만원 → 원
                        except (ValueError, AttributeError):
                            pass
                    break

        # ── 转换为 USD ──
        market_cap_usd = market_cap_krw / KRW_USD_RATE if market_cap_krw else None
        market_cap_raw_usd = market_cap_usd  # raw USD
        # Naver: market_cap_b 以 亿(100M)为单位存储，与腾讯 API 保持一致的存储格式
        # 1 B = 10 亿, 所以 USD billions × 10 = 亿
        market_cap_b_yi = round(market_cap_usd / 1e8, 2) if market_cap_usd else None  # 亿单位 (= B × 10)

        # ── 提取 52周高低 ──
        high_52w_str = infos.get("highPriceOf52Weeks", {}).get("value", "0")
        low_52w_str = infos.get("lowPriceOf52Weeks", {}).get("value", "0")
        high_52w = float(high_52w_str.replace(",", "")) if high_52w_str else None
        low_52w = float(low_52w_str.replace(",", "")) if low_52w_str else None

        # ── 提取外資持股比例 ──
        foreign_rate_str = infos.get("foreignRate", {}).get("value", "0%")
        foreign_rate = float(foreign_rate_str.replace("%", "")) if foreign_rate_str else None

        return {
            "ticker": ticker,
            "kr_code": kr_code,
            "current_price": current_price,           # local currency (KRW)
            "current_price_usd": round(current_price / KRW_USD_RATE, 2) if current_price else None,  # USD equivalent
            "change_pct": change_pct,
            "pe_ttm": pe_ttm,
            "eps": eps,
            "market_cap": market_cap_usd,          # raw USD
            "market_cap_b": market_cap_b_yi,       # 亿单位(100M), 与腾讯API一致
            "market_cap_krw": market_cap_krw,
            "market_cap_krw_text": market_cap_text,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "foreign_rate": foreign_rate,
            "currency": "KRW",
            "source": "naver",
        }
    except Exception as e:
        logger.warning(f"naver korean info fetch failed for {ticker}: {e}")
    return None


def _parse_tencent_quote(ticker: str) -> Optional[dict]:
    """获取腾讯财经实时行情并解析为结构化数据"""
    tencent_code = TENCENT_US_MAP.get(ticker.upper())
    if not tencent_code:
        return None

    try:
        url = f"https://qt.gtimg.cn/q={tencent_code}"
        req = urllib.request.Request(url, headers={"User-Agent": TENCENT_UA})
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode("gbk")

        # 解析: v_code="f1~f2~...~fN";
        if "=\"" not in raw:
            return None
        body = raw.split("=\"", 1)[1].rsplit("\"", 1)[0] if "\"" in raw else ""
        fields = body.split("~")

        if len(fields) < 46:
            return None

        def sf(i):
            """安全取字段并转 float"""
            try:
                return float(fields[i].strip()) if fields[i].strip() else None
            except (ValueError, IndexError):
                return None

        price = sf(3)
        prev_close = sf(4)
        change_pct = sf(32)
        pe = sf(39)
        mcap_raw = sf(45)       # 总市值（单位取决于股票）
        name = fields[1] if len(fields) > 1 else ticker
        high = sf(33)
        low = sf(34)
        volume = sf(6)          # 成交量（手）

        # 总市值单位处理: 腾讯 API 中 US 股票总市值以 亿(100M)为单位
        # 统一乘以 1e8 转换为美元
        market_cap_raw = sf(45)
        if market_cap_raw:
            market_cap = market_cap_raw * 1e8
        else:
            market_cap = None

        return {
            "ticker": ticker,
            "name": name.strip(),
            "current_price": price,
            "change_pct": change_pct,
            "prev_close": prev_close,
            "high": high,
            "low": low,
            "volume": volume,
            "pe_ttm": pe,
            "market_cap": market_cap,
            "market_cap_b": round(market_cap / 1e8, 2) if market_cap else None,
            "source": "tencent",
        } if price is not None else None
    except Exception as e:
        logger.warning(f"tencent quote fetch failed for {ticker}: {e}")
    return None


def fetch_price_history(ticker: str,
                        days: int = 90,
                        interval: str = "1d") -> list[dict]:
    """
    获取股票历史价格数据（多数据源自动切换）
    策略:
      1. 如果是 A 股代码（6位数字），用 akshare
      2. 如果是港股代码（hk_开头），用 akshare
      3. 如果是 US 股票（在 TENCENT_US_MAP 中），用腾讯财经 API
      4. 否则用 yfinance

    Returns: [{"date": "2024-01-01", "price": 150.0, "change_pct": 0.5, "volume": 1000000, "source": "yfinance"}, ...]
    """
    if not ticker:
        return []

    clean_ticker = ticker.upper()

    # 1) 韩国股票: FinanceDataReader (优先)
    if clean_ticker in NAVER_KOREAN_MAP:
        try:
            import FinanceDataReader as fdr
            end = datetime.now()
            start = end - timedelta(days=days)
            df = fdr.DataReader(NAVER_KOREAN_MAP[clean_ticker],
                                 start.strftime("%Y-%m-%d"),
                                 end.strftime("%Y-%m-%d"))
            if df is not None and not df.empty:
                result = []
                prev_close = None
                for idx, row in df.iterrows():
                    d = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
                    close = round(float(row.get("Close", 0)), 2)
                    change = round((close - prev_close) / prev_close * 100, 2) if prev_close else None
                    result.append({
                        "date": d,
                        "price": close,
                        "change_pct": change,
                        "volume": int(row.get("Volume", 0)),
                        "source": "financedatareader",
                    })
                    prev_close = close
                if result:
                    logger.info(f"Using FinanceDataReader for Korean stock: {clean_ticker}")
                    return result
        except ImportError:
            logger.warning("FinanceDataReader not installed; falling back for Korean stock")
        except Exception as e:
            logger.warning(f"FinanceDataReader failed for {clean_ticker}: {e}")

    # 1) A 股代码检测
    a_share_code = None
    if clean_ticker.endswith(".SH") or clean_ticker.endswith(".SZ"):
        a_share_code = clean_ticker.replace(".SH", "").replace(".SZ", "")
    elif clean_ticker.isdigit() and len(clean_ticker) == 6:
        a_share_code = clean_ticker
    elif clean_ticker in A_SHARE_MAP:
        a_share_code = A_SHARE_MAP[clean_ticker]

    if a_share_code:
        logger.info(f"Using akshare for A-share: {a_share_code}")
        result = _fetch_akshare_a_share(a_share_code, days)
        if result:
            return result
        logger.info(f"akshare returned no data for {a_share_code}, trying yfinance")

    # 2) 港股检测
    hk_code = HK_TICKER_MAP.get(clean_ticker)
    if hk_code:
        logger.info(f"Using akshare for HK: {hk_code}")
        result = _fetch_akshare_hk(hk_code.replace("hk_", ""), days)
        if result:
            return result

    # 3) US 股票: 腾讯财经 API (优先于 yfinance 因为 yfinance 常被限流)
    if clean_ticker in TENCENT_US_MAP:
        logger.info(f"Using Tencent API for US: {clean_ticker}")
        result = _fetch_tencent_kline(clean_ticker, days)
        if result:
            return result
        logger.info(f"Tencent returned no data for {clean_ticker}, trying yfinance")

    # 4) 默认用 yfinance (支持 YFINANCE_TICKER_MAP 中的特殊 ticker)
    if HAS_YFINANCE:
        yf_ticker = YFINANCE_TICKER_MAP.get(clean_ticker, ticker)
        result = _fetch_yfinance(yf_ticker, days, interval)
        if result:
            return result

    # 5) 最终 fallback
    logger.warning(f"All data sources exhausted for {ticker}")
    return []


def get_current_price(ticker: str) -> Optional[float]:
    """快速获取当前价格（多数据源）"""
    if not ticker:
        return None

    clean_ticker = ticker.upper()

    # 韩国股票: Naver Mobile API
    if clean_ticker in NAVER_KOREAN_MAP:
        kr_info = _fetch_naver_korean_info(clean_ticker)
        if kr_info and kr_info.get("current_price"):
            return kr_info["current_price"]

    # A 股: 用 akshare 实时行情
    a_share_code = None
    if clean_ticker.endswith(".SH") or clean_ticker.endswith(".SZ"):
        a_share_code = clean_ticker.replace(".SH", "").replace(".SZ", "")
    elif clean_ticker.isdigit() and len(clean_ticker) == 6:
        a_share_code = clean_ticker
    elif clean_ticker in A_SHARE_MAP:
        a_share_code = A_SHARE_MAP[clean_ticker]

    if a_share_code and HAS_AKSHARE:
        try:
            df = ak.stock_zh_a_hist(symbol=a_share_code, period="daily",
                                     start_date=(datetime.now() - timedelta(days=5)).strftime("%Y%m%d"),
                                     end_date=datetime.now().strftime("%Y%m%d"),
                                     adjust="qfq")
            if df is not None and not df.empty:
                return round(float(df["收盘"].iloc[-1]), 2)
        except Exception as e:
            logger.warning(f"akshare current price failed for {a_share_code}: {e}")

    # US 股票: 腾讯财经 API
    if clean_ticker in TENCENT_US_MAP:
        quote = _parse_tencent_quote(clean_ticker)
        if quote and quote.get("current_price"):
            return quote["current_price"]

    # 其他: yfinance
    if HAS_YFINANCE:
        try:
            stock = yf.Ticker(ticker)
            info = stock.history(period="1d")
            if not info.empty:
                return round(float(info["Close"].iloc[-1]), 2)
        except Exception as e:
            logger.warning(f"yfinance current price failed for {ticker}: {e}")

    return None


def get_stock_info(ticker: str) -> dict:
    """获取股票基本信息（市值、PE、PS等），多数据源"""
    if not ticker:
        return {}

    result = {"source": None, "ticker": ticker}
    clean_ticker = ticker.upper()

    # 韩国股票: Naver Mobile API (优先)
    if clean_ticker in NAVER_KOREAN_MAP:
        kr_info = _fetch_naver_korean_info(clean_ticker)
        if kr_info and kr_info.get("current_price") is not None:
            result.update({
                "current_price": kr_info.get("current_price"),
                "current_price_usd": kr_info.get("current_price_usd"),
                "change_pct": kr_info.get("change_pct"),
                "pe_ttm": kr_info.get("pe_ttm"),
                "market_cap": kr_info.get("market_cap"),
                "market_cap_b": kr_info.get("market_cap_b"),
                "eps": kr_info.get("eps"),
                "short_name": f"KR:{kr_info.get('kr_code')}",
                "currency": "KRW",
                "source": "naver",
            })
            return result

    # US 股票: 腾讯财经 API (优先, 更稳定)
    if clean_ticker in TENCENT_US_MAP:
        quote = _parse_tencent_quote(clean_ticker)
        if quote and quote.get("current_price") is not None:
            result.update({
                "market_cap": quote.get("market_cap"),
                "market_cap_b": quote.get("market_cap_b"),
                "pe_ttm": quote.get("pe_ttm"),
                "current_price": quote.get("current_price"),
                "change_pct": quote.get("change_pct"),
                "short_name": quote.get("name"),
                "source": "tencent",
            })
            return result

    # 尝试 yfinance 获取完整信息
    if HAS_YFINANCE:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            if info and info.get("marketCap"):
                result.update({
                    "market_cap": info.get("marketCap"),
                    "market_cap_b": round(info.get("marketCap", 0) / 1e8, 2) if info.get("marketCap") else None,
                    "pe_ttm": info.get("trailingPE"),
                    "ps_ttm": info.get("priceToSalesTrailing12Months"),
                    "pb": info.get("priceToBook"),
                    "dividend_yield": info.get("dividendYield"),
                    "enterprise_value": info.get("enterpriseValue"),
                    "ev_ebitda": info.get("enterpriseToEbitda"),
                    "revenue": info.get("totalRevenue"),
                    "revenue_b": round(info.get("totalRevenue", 0) / 1e8, 2) if info.get("totalRevenue") else None,
                    "net_income": info.get("netIncomeToCommon"),
                    "net_income_b": round(info.get("netIncomeToCommon", 0) / 1e8, 2) if info.get("netIncomeToCommon") else None,
                    "sector": info.get("sector"),
                    "industry": info.get("industry"),
                    "short_name": info.get("shortName"),
                    "long_name": info.get("longName"),
                    "source": "yfinance",
                })
                return result
        except Exception as e:
            logger.warning(f"yfinance info failed for {ticker}: {e}")

    # 尝试 akshare A 股信息
    a_share_code = None
    if clean_ticker.endswith(".SH") or clean_ticker.endswith(".SZ"):
        a_share_code = clean_ticker.replace(".SH", "").replace(".SZ", "")
    elif clean_ticker.isdigit() and len(clean_ticker) == 6:
        a_share_code = clean_ticker
    elif clean_ticker in A_SHARE_MAP:
        a_share_code = A_SHARE_MAP[clean_ticker]

    if a_share_code and HAS_AKSHARE:
        try:
            # 获取实时行情
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                # 筛选代码
                row = df[df["代码"] == a_share_code]
                if not row.empty:
                    r = row.iloc[0]
                    result.update({
                        "market_cap": r.get("总市值"),
                        "market_cap_b": round(float(r.get("总市值", 0)) / 1e8, 2) if r.get("总市值") else None,
                        "pe_ttm": r.get("市盈率-动态"),
                        "ps_ttm": r.get("市销率"),
                        "pb": r.get("市净率"),
                        "short_name": r.get("名称"),
                        "current_price": r.get("最新价"),
                        "change_pct": r.get("涨跌幅"),
                        "volume": r.get("成交量"),
                        "turnover": r.get("成交额"),
                        "source": "akshare",
                    })
                    return result
        except Exception as e:
            logger.warning(f"akshare info failed for {a_share_code}: {e}")

    return result


def get_top_gainers_losers(top_n: int = 10) -> dict:
    """
    获取A股市场热门股票涨跌榜（通过AKShare）
    用于 Dashboard 展示市场情绪
    """
    if not HAS_AKSHARE:
        return {"gainers": [], "losers": []}
    try:
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return {"gainers": [], "losers": []}

        # 过滤掉ST、退市等
        df = df[~df["名称"].str.contains("ST|退市", na=False)]

        # 涨跌幅列
        change_col = "涨跌幅"
        if change_col not in df.columns:
            return {"gainers": [], "losers": []}

        df[change_col] = pd.to_numeric(df[change_col], errors="coerce")

        gainers = df.nlargest(top_n, change_col)[["代码", "名称", "最新价", "涨跌幅"]].to_dict("records")
        losers = df.nsmallest(top_n, change_col)[["代码", "名称", "最新价", "涨跌幅"]].to_dict("records")

        return {
            "gainers": [{"code": g["代码"], "name": g["名称"], "price": float(g["最新价"]), "change_pct": float(g["涨跌幅"])} for g in gainers],
            "losers": [{"code": l["代码"], "name": l["名称"], "price": float(l["最新价"]), "change_pct": float(l["涨跌幅"])} for l in losers],
        }
    except Exception as e:
        logger.warning(f"akshare top gainers/losers failed: {e}")
    return {"gainers": [], "losers": []}


# ── DB 缓存层 ─────────────────────────────────────────────────────

def _read_from_cache(db, ticker: str, days: int) -> list[dict] | None:
    """从 PriceCache 表读取历史价格"""
    try:
        from models import PriceCache
        from sqlalchemy import desc
        from datetime import timedelta

        cutoff = datetime.now().date() - timedelta(days=days)
        rows = (
            db.query(PriceCache)
            .filter(PriceCache.ticker == ticker.upper(), PriceCache.date >= cutoff)
            .order_by(PriceCache.date)
            .all()
        )
        if not rows:
            return None
        return [
            {
                "date": r.date.strftime("%Y-%m-%d") if hasattr(r.date, "strftime") else str(r.date),
                "price": r.price,
                "change_pct": r.change_pct,
                "volume": r.volume,
                "source": r.source,
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning(f"cache read failed for {ticker}: {e}")
    return None


def _write_to_cache(db, ticker: str, data: list[dict], source: str):
    """写入 PriceCache 表 (upsert by ticker+date)"""
    try:
        from models import PriceCache
        from datetime import datetime as dt

        ticker = ticker.upper()
        today = dt.now().date()
        for d in data:
            try:
                d_date = dt.strptime(d["date"], "%Y-%m-%d").date()
            except (ValueError, KeyError):
                continue
            existing = (
                db.query(PriceCache)
                .filter(PriceCache.ticker == ticker, PriceCache.date == d_date)
                .first()
            )
            if existing:
                existing.price = d.get("price", existing.price)
                existing.change_pct = d.get("change_pct")
                existing.volume = d.get("volume")
                existing.source = source
                existing.updated_at = today
            else:
                db.add(PriceCache(
                    ticker=ticker,
                    date=d_date,
                    price=d.get("price", 0),
                    change_pct=d.get("change_pct"),
                    volume=d.get("volume"),
                    source=source,
                    updated_at=today,
                ))
        db.commit()
    except Exception as e:
        logger.warning(f"cache write failed for {ticker}: {e}")
        db.rollback()


def _read_stock_info_cache(db, ticker: str) -> dict | None:
    """从 StockInfoCache 读取"""
    try:
        from models import StockInfoCache
        row = db.query(StockInfoCache).filter(StockInfoCache.ticker == ticker.upper()).first()
        if row and row.data_json:
            return row.data_json
    except Exception as e:
        logger.warning(f"stock info cache read failed for {ticker}: {e}")
    return None


def _write_stock_info_cache(db, ticker: str, data: dict):
    """写入 StockInfoCache"""
    try:
        from models import StockInfoCache
        from datetime import datetime as dt

        ticker = ticker.upper()
        existing = db.query(StockInfoCache).filter(StockInfoCache.ticker == ticker).first()
        if existing:
            existing.data_json = data
            existing.updated_at = dt.now().date()
        else:
            db.add(StockInfoCache(
                ticker=ticker,
                data_json=data,
                updated_at=dt.now().date(),
            ))
        db.commit()
    except Exception as e:
        logger.warning(f"stock info cache write failed for {ticker}: {e}")
        db.rollback()


def get_price_history_cached(ticker: str, days: int, db) -> list[dict]:
    """
    带缓存的历史价格主入口
    策略: live fetch → write cache → return; 若 live 失败则读 cache → return; 否则 []
    """
    live = fetch_price_history(ticker, days)
    if live:
        _write_to_cache(db, ticker, live, live[0].get("source", "live"))
        return live

    cached = _read_from_cache(db, ticker, days)
    if cached:
        logger.info(f"cache hit for {ticker} ({days}d), source={cached[0].get('source')}")
        return cached

    return []


def get_stock_info_cached(ticker: str, db) -> dict:
    """
    带缓存的股票信息主入口
    策略: live fetch → write cache → return; 若 live 失败则读 cache → return
    """
    live = get_stock_info(ticker)
    if live and live.get("source"):
        _write_stock_info_cache(db, ticker, live)
        return live

    cached = _read_stock_info_cache(db, ticker)
    if cached:
        logger.info(f"stock info cache hit for {ticker}")
        return cached

    return live or {}
