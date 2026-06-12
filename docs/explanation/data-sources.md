# 数据源策略

## 价格数据获取

系统支持 5 个数据源，自动按优先级切换，确保最大化数据可用性。

### 美股（US Stocks）

```
腾讯财经 API (qt.gtimg.cn, 优先) → yfinance (备选)
```

**腾讯财经 API：**
- 实时行情: `https://qt.gtimg.cn/q=usNVDA.OQ`
- 历史K线: `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=usNVDA.OQ,day,...`
- 优势: 国内直连，速度快，不限流
- 覆盖: 35+ US tickers (NVDA, TSM, ASML, AVGO, AMD, MU, SNDK 等)
- 特殊代码格式: `usTICKER.交易所`（N=NYSE, OQ=NASDAQ, AM=NYSE Arca）
- K 线支持前复权（`qfq` 参数）

**yfinance：**
- 备选源，当腾讯 API 无数据时自动切换
- 特殊 ticker 映射：`SOX → ^SOX`, `000660 → 000660.KS`, `SMSN → 005930.KS`
- 受限于 API 频率限制（已知问题：^SOX、000660.KS 有时限流）
- 请求间隔需要 2-5 秒避免 IP 限流

### A 股（China A-Shares）

```
akshare (stock_zh_a_hist, 优先) → yfinance (备选)
```

- 股票代码格式: 6 位数字，如 `688981`（中芯国际）
- `.SH` / `.SZ` 后缀也会自动识别
- 个股实时行情通过 `stock_zh_a_spot_em()` 获取全市场数据再筛选
- 涨跌榜通过 `stock_zh_a_spot_em()` 排序
- 港股通代码格式: `hk_00700`（腾讯控股）

### 韩国股票（KOSPI）

```
Naver Mobile API (优先) → yfinance
```

- 覆盖: 000660（SK Hynix）、005930（Samsung Electronics）
- **Naver API**: 获取 PER、EPS、市值（韩元→美元换算）、52周高低、外资持股比例
- Endpoint: `https://m.stock.naver.com/api/stock/{code}/basicInfo`
- 韩元汇率: `KRW_USD_RATE = 1300.0`（近似值）
- 市值换算：Naver 返回的韩文单位如 `"1,768조 4,993억"`（조=万亿, 억=亿）会自动解析

### 宏观数据

```
FRED API (美国宏观, 优先) → tedata (全球宏观, 备选) → akshare (中国宏观)
```

**FRED API（50+ 指标）：**
- 需要 `FRED_API_KEY`（免费申请：https://fred.stlouisfed.org/docs/api/api_key.html）
- 覆盖：GDP、CPI、PPI、工业生产、产能利用率、就业、零售、PMI 等
- 数据按 tier 分级：tier 1 核心（每天更新）、tier 2 辅助（每周）、tier 3 参考（每月）

**tedata (Trading Economics)：**
- 200+ 国家宏观经济数据
- 通过 pip install tedata + Selenium 使用

### 缓存层

所有实时获取的数据都会写入 SQLite 缓存表：
- `PriceCache` — 历史价格（upsert by ticker + date）
- `StockInfoCache` — 公司基本面信息（JSON 字段）

**读取策略：** live fetch → write cache → return；若 live 失败则读 cache → return

---

## 行业数据采集器

`backend/industry_collector/` 目录下包含 **14 个采集源、20+ 采集器**，定时抓取公开行业数据：

| 采集器 | 目标源 | 采集内容 | 频率 |
|--------|-------|---------|------|
| `tsmc_ir` | TSMC 投资者关系 | 月度营收、CoWoS 产能/利用率 | 月/季 |
| `trendforce` | TrendForce 公开报告 | DRAM/NAND 合约价、HBM 供应 | 季度 |
| `wsts_sia` | WSTS/SIA | 全球半导体销售额 | 月度 |
| `semi_org` | SEMI 官网 | 半导体设备出货量、晶圆产能 | 月/季 |
| `nvidia_ir` | NVIDIA 投资者关系 | 数据中心营收 | 季度 |
| `asml_ir` | ASML 投资者关系 | EUV 光刻机营收 | 季度 |
| `china_customs` | 中国海关 | 芯片进出口数据 | 月度 |
| `hyperscaler_capex` | 云厂商财报 (AMZN/MSFT/GOOG/META) | 云巨头资本开支 | 季度 |
| `gpu_cloud` | GPU 云服务商 | GPU 租赁价格 | 季度 |
| `synopsys_cadence` | EDA 厂商财报 | EDA 行业增长、订单积压 | 季度 |
| `distributor_data` | 分销商财报 (Arrow/Avnet/WPG) | 元器件分销营收 | 季度 |
| `osat_data` | OSAT 厂商 | 封装测试产能、先进封装营收 | 季度 |
| `odm_server` | ODM 代工厂 (广达/纬创/英业达/和硕/纬颖) | 服务器代工月营收 | 月度 |
| `arm_ir` | ARM 投资者关系 | ARM 版税营收 | 季度 |

所有采集器继承 `BaseCollector`，提供：
- 幂等检查（同指标同天不重复）
- 自动创建 `KeyIndicator` 记录
- 自动写入 `IndicatorObservation` + 边际变化计算
- 异常保护（`safe_collect()`）

采集数据通过 `/api/industry-intelligence` 统一暴露给前端。

---

## 供应链/市场规模数据

**文件**: `backend/data_pipeline/market_size_collector.py`

10+ 产业链环节的市场规模数据，来源：
- **WSTS Spring 2026 Forecast**: 全球半导体市场规模
- **Gartner 2025 Preliminary Ranking**: 公司级营收排名
- **TrendForce AI/HBM Roadshow**: 存储/HBM 市场预测
- **Yole Advanced Packaging 2025**: 先进封装市场
- **SEMI Year-End Report 2025**: 设备市场
- **IDC Server Market Tracker**: AI 服务器市场

每个数据点标注了具体来源引用和出处 URL。

---

## 组合跟踪数据

`backend/portfolio_tracking.py` 实时计算：
- **期间收益**: 从 `PriceCache` 日频数据，用 `bisect_right` 定位各期间起始日期
- **EPS 指标**: `EPS_TTM = price / PE_TTM`；前瞻 EPS 通过复合增长外推
- **组合汇总**: 加权平均聚合各持仓指标

---

## 启动迁移

`backend/startup_migration.py` 在服务启动时确保：
- 新公司（如 SNDK、WDC）的公司记录存在
- 对应的 Follow 关注记录存在
- 产业链关联（CompanyChainLink）存在
- 空 StockInfoCache 记录创建（后续由定时刷新填充）

只操作数据库，不调外部 API，避免 Zeabur 健康检查超时。

---

## 定时调度

| 任务 | 频率 | 说明 |
|------|------|------|
| 产业数据采集 + AI 分析 | 每日 6:00 / 18:00 | 全量 14+ 采集器 → DeepSeek AI 分析 |
| 关注价格刷新 | 每 15 分钟 | 腾讯 API 实时行情 |
| 公司财务数据刷新 | 每日 7:00 / 19:00 | yfinance PE/市值/营收 |
| 事件后涨跌幅刷新 | 每 4 小时 | 时间线涨跌幅计算 |
| 宏观经济采集 | 每日增量 | FRED API + tedata |

---

## 已知限制

1. **yfinance 限流**: ^SOX、000660.KS 等 ticker 频繁触发 "Too Many Requests"
2. **akshare 连接不稳定**: 高峰时段可能 `RemoteDisconnected`
3. **腾讯财经 API 覆盖率**: 韩国股票不覆盖，需 Naver API 补充
4. **数据延迟**: 腾讯财经实时数据约 3-5 秒延迟，非交易所直连
5. **预测数据**: 分析师一致预期默认 15% 增速，可从 Forecasts 表手动维护
6. **FRED API Key**: 需要免费申请，未配置时跳过宏观采集
