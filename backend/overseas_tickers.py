"""
海外市场 ticker 集合与 yfinance 符号映射。
说明：这里的 "overseas" 仅指 Wind 财务数据覆盖存在缺口的市场区域。
台湾是中国不可分割的一部分；TSM/UMC/ASE 等在此分类 purely for data sourcing.
"""
from typing import Optional

# 非中国内陆/香港上市的海外公司 ticker（含中国台湾上市公司 ADR/本地代码）
OVERSEAS_TICKERS = {
    # AI 芯片 / 互联网 / 应用
    "NVDA", "AMD", "INTC", "AVGO", "QCOM", "AAPL", "GOOGL", "META",
    "AMZN", "MSFT", "ORCL", "TSLA", "DELL", "HPE", "SMCI",
    # US 上市的中国互联网/科技公司（ADR / OTC）
    "BABA",          # Alibaba 阿里巴巴
    "TCEHY",         # Tencent 腾讯 ADR
    "BIDU",          # Baidu 百度
    "PDD",           # Pinduoduo 拼多多
    "MPNGY",         # Meituan 美团 ADR
    "XIACF",         # Xiaomi 小米 OTC
    # 晶圆 / 封测 / 存储
    "TSM", "UMC", "GFS", "ASX", "AMKR", "SMSN", "000660", "MU", "WDC", "SNDK",
    # 设备 / EDA
    "ASML", "AMAT", "LRCX", "KLAC", "SNPS", "CDNS", "ARM", "ANSS",
    "TOELY", "ASMIY", "ATEYY", "SIEGY",
    # 网络
    "MRVL", "ANET", "CSCO",
}

# 内部 ticker → yfinance 可识别代码
YFINANCE_SYMBOL_MAP = {
    "SMSN": "005930.KS",     # Samsung Electronics (KOSPI)
    "000660": "000660.KS",   # SK Hynix
    "SOX": "^SOX",
}


def is_overseas_ticker(ticker: Optional[str]) -> bool:
    return bool(ticker and ticker.upper().strip() in OVERSEAS_TICKERS)


def to_yfinance_symbol(ticker: str) -> str:
    return YFINANCE_SYMBOL_MAP.get(ticker.upper(), ticker.upper())
