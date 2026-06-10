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
- 覆盖: 70+ US tickers (NVDA, TSM, ASML, AVGO, AMD, MU, 等)
- 特殊代码格式: `usTICKER.交易所`（N=NYSE, OQ=NASDAQ, AM=NYSE Arca）

**yfinance：**
- 备选源，当腾讯 API 无数据时自动切换
- 特殊 ticker 映射：`SOX → ^SOX`, `000660 → 000660.KS`, `SMSN → 005930.KS`
- 受限于 API 频率限制（已知问题：^SOX、000660.KS 有时限流）

### A 股（China A-Shares）

```
akshare (stock_zh_a_hist, 优先) → yfinance (备选)
```

- 股票代码格式: 6 位数字，如 `688981`（中芯国际）
- `.SH` / `.SZ` 后缀也会自动识别
- 个股实时行情通过 `stock_zh_a_spot_em()` 获取全市场数据再筛选
- 涨跌榜通过 `stock_zh_a_spot_em()` 排序

### 港股（Hong Kong）

```
akshare (stock_hk_hist) → yfinance
```

- 代码格式: `hk_00700`（腾讯控股）
- 通过 `HK_TICKER_MAP` 将美股 ADR ticker 映射到港股代码

### 韩国股票（KOSPI）

```
Naver Mobile API (优先) → FinanceDataReader → yfinance
```

- 覆盖: 000660（SK Hynix）、005930（Samsung Electronics）
- **Naver API**: 获取 PER、EPS、市值（韩元→美元换算）、52周高低、外资持股比例
- 韩元汇率: `KRW_USD_RATE = 1300.0`（近似值）
- 市值换算：Naver 返回的韩文单位如 `"1,768조 4,993억"`（조=万亿, 억=亿）会自动解析

### 缓存层

所有实时获取的数据都会写入 SQLite 缓存表：
- `PriceCache` — 历史价格（upsert by ticker + date）
- `StockInfoCache` — 公司基本面信息

**读取策略：** live fetch → write cache → return；若 live 失败则读 cache → return

---

## 行业数据采集器

`backend/industry_collector/` 目录下包含 14 个采集模块，定时抓取公开行业数据：

| 采集器 | 目标源 | 采集内容 |
|--------|-------|---------|
| `asml_ir` | ASML 投资者关系 | EUV 光刻机出货量、营收 |
| `china_customs` | 中国海关 | 芯片进出口数据 |
| `distributor_data` | 分销商库存报告 | 元器件交期、价格趋势 |
| `gpu_cloud` | GPU 云服务商 | GPU 租赁价格、供应 |
| `hyperscaler_capex` | 云厂商财报 | AWS/Azure/GCP 资本开支 |
| `nvidia_ir` | NVIDIA 投资者关系 | GPU 营收、数据中心业务 |
| `osat_data` | OSAT 厂商 | 封装测试产能利用率 |
| `semi_org` | SEMI 官网 | 半导体设备出货量 |
| `synopsys_cadence` | EDA 厂商财报 | EDA 行业增长 |
| `trendforce` | TrendForce 公开报告 | DRAM/NAND 价格、HBM 供应 |
| `tsmc_ir` | TSMC 投资者关系 | 产能利用率、制程节点营收 |
| `wsts_sia` | WSTS/SIA | 全球半导体销售额 |

采集数据经过 `KeyIndicator` + `IndicatorObservation` 模型存储，通过 `/api/industry-intelligence` 统一暴露给前端。

---

## 供应链数据

产业链环节数据（市场容量、供需缺口、增长驱动力）通过 `seed_data.py` 的 `seed_industry_chain_links()` 导入。

数据来源整合自：
- **WSTS/SIA**: 半导体市场规模和增长数据
- **TrendForce**: 存储芯片价格和供需
- **SEMI**: 设备出货量
- **Gartner/IDC**: IT 基础设施资本开支
- **IC Insights**: 集成电路市场分析

---

## 已知限制

1. **yfinance 限流**: ^SOX、000660.KS 等 ticker 频繁触发 "Too Many Requests"。备选方案：Wind MCP（已配置 API Key）
2. **akshare 连接不稳定**: 高峰时段可能 `RemoteDisconnected`
3. **腾讯财经 API 覆盖率**: 韩国股票不覆盖，需 Naver API 补充
4. **数据延迟**: 腾讯财经实时数据约 15 分钟延迟
5. **预测数据**: 分析师一致预期为手动维护，非实时更新
