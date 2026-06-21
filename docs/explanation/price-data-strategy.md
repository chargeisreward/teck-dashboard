# 行情数据的多源获取与降级策略

## 问题

单一免费行情 API 不可靠：yfinance 限流严重，A 股需要国内数据源，韩国股票需要本地 API。如果某个源失败就返回空，会导致大量页面（Dashboard、产业链、投资组合）出现空白。

## 策略总览

`backend/price_data.py` 实现了按市场和 ticker 的优先级链：

| 市场 | 第一优先 | 第二优先 | 备注 |
|---|---|---|---|
| 美股 | 腾讯财经 API | yfinance | 腾讯更稳定，yfinance 限流 |
| 港股 | akshare `stock_hk_hist` | yfinance | 通过 `HK_TICKER_MAP` 映射 |
| A 股 | akshare `stock_zh_a_hist` | yfinance | 6 位数字代码或 `.SH/.SZ` |
| 韩国股 | Naver Mobile API | yfinance | KOSPI 代码，如 000660/005930 |
| 指数/特殊 | yfinance（经 `YFINANCE_TICKER_MAP`） | — | 如 `SOX` → `^SOX` |

`get_stock_info` 与 `fetch_price_history` 的优先级略有不同，因为实时信息（市值、PE）与历史 K 线的可用源不同。

## `fetch_price_history` 调用链

1. 若 ticker 在 `A_SHARE_MAP` 或匹配 6 位数字 / `.SH/.SZ`，使用 akshare A 股。
2. 若 ticker 在 `HK_TICKER_MAP`，使用 akshare 港股。
3. 若 ticker 在 `TENCENT_US_MAP`，使用腾讯 K 线。
4. 否则使用 yfinance。
5. 全部失败返回空列表。

## `get_stock_info` 调用链

1. 若 ticker 在 `NAVER_KOREAN_MAP`，使用 Naver API（SK Hynix、Samsung）。
2. 若 ticker 在 `TENCENT_US_MAP`，使用腾讯实时报价。
3. 否则尝试 yfinance `info`。
4. 若仍失败且为 A 股，尝试 akshare 实时行情。
5. 返回包含 `current_price`、`market_cap`、`pe_ttm`、`source` 等字段的字典。

## 缓存策略

### PriceCache

- 写入 `_write_to_cache(db, ticker, data, source, overwrite=False)`。
- 默认 `overwrite=False`：首次成功抓取的数据不会被后续可能不完整的响应覆盖。适用于日常增量补缺口。
- `overwrite=True`：用于一次性 backfill，替换已有数据。

### StockInfoCache

- `get_stock_info` 在 `refresh_company_data.py` 等调用方中被缓存到 `StockInfoCache.data_json`。
- 缓存粒度为 ticker 最新快照，无历史版本。

## 单位约定

- `PriceCache.price` 存储实际成交价（美元或当地货币）。
- `StockInfoCache.data_json` 中 `market_cap_b` 以 **亿**（= billion USD × 10）存储。例如 TSMC 市值约 8000 亿美元 → `market_cap_b` ≈ 80000。
- Naver 返回韩元市值，按硬编码 `KRW_USD_RATE = 1300.0` 换算为美元后再转为 亿。

## 错误处理

- 每个 `_fetch_*` 函数内部 try/except，失败返回空列表/None。
- 主调用链依次尝试下一个源，不会抛异常中断。
- 日志记录 warning，便于排查具体源失败。

## 设计取舍

| 权衡点 | 选择 | 代价 |
|---|---|---|
| 多源复杂度 vs 稳定性 | 4 个数据源 + 映射表 | 新增 ticker 需要在多处维护映射 |
| 缓存不覆盖 vs 数据新鲜 | 默认不覆盖 | 需要手动触发 `overwrite=True` 的全量回填 |
| 免费 API vs 付费数据质量 | 免费 API | 偶尔限流、字段缺失、汇率近似 |
| 韩国股票汇率 | 硬编码 1300 KRW/USD | 市值绝对值有轻微误差 |

## 如何新增 ticker

1. 确定市场，加入 `TENCENT_US_MAP`、`NAVER_KOREAN_MAP`、`A_SHARE_MAP` 或 `HK_TICKER_MAP`。
2. 在 `frontend/src/pages/PortfolioPage.jsx` 的 `TICKER_COLORS` 中分配颜色。
3. 运行 `python backfill_3y_prices.py` 回填历史价格。

## 相关

- [数据源策略](data-sources.md) — 产业数据采集器
- [如何排查常见问题](../how-to/index.md#如何排查常见问题)
- [配置参考](../reference/configuration.md)
