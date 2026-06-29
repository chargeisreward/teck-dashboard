from overseas_tickers import is_overseas_ticker, to_yfinance_symbol


def test_is_overseas_ticker_includes_us_and_chinese_adrs():
    """美股 + US 上市的中国公司 ADR 都属于 overseas（都走 yfinance 补缺）。"""
    # 美股
    assert is_overseas_ticker("NVDA") is True
    assert is_overseas_ticker("AAPL") is True
    # 中国台湾 ADR
    assert is_overseas_ticker("TSM") is True
    # US 上市的中国公司 ADR/OTC（Wind 数据曾有 FX bug，改走 yfinance）
    assert is_overseas_ticker("BABA") is True   # Alibaba 阿里巴巴
    assert is_overseas_ticker("TCEHY") is True  # Tencent 腾讯
    assert is_overseas_ticker("BIDU") is True   # Baidu 百度
    assert is_overseas_ticker("PDD") is True    # Pinduoduo 拼多多
    # 韩国本地代码
    assert is_overseas_ticker("000660") is True  # SK Hynix
    assert is_overseas_ticker("SMSN") is True    # Samsung
    # 空值
    assert is_overseas_ticker(None) is False
    assert is_overseas_ticker("") is False


def test_to_yfinance_symbol_maps_korea():
    assert to_yfinance_symbol("SMSN") == "005930.KS"
    assert to_yfinance_symbol("000660") == "000660.KS"
    assert to_yfinance_symbol("NVDA") == "NVDA"
