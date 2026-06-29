from overseas_tickers import is_overseas_ticker, to_yfinance_symbol


def test_is_overseas_excludes_chinese_adrs():
    assert is_overseas_ticker("NVDA") is True
    assert is_overseas_ticker("TSM") is True
    assert is_overseas_ticker("BABA") is False  # 中国公司 ADR，不在 overseas 集合
    assert is_overseas_ticker(None) is False


def test_to_yfinance_symbol_maps_korea():
    assert to_yfinance_symbol("SMSN") == "005930.KS"
    assert to_yfinance_symbol("000660") == "000660.KS"
    assert to_yfinance_symbol("NVDA") == "NVDA"
