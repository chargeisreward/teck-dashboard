# 数据库参考

> SQLite 数据库文件: `backend/teck_dashboard.db`（本地) / `/data/teck_dashboard.db`（Zeabur 生产）
> ORM: SQLAlchemy 2.0+
> 模型定义: `backend/models.py`
> 种子数据: 通过启动迁移 + 采集器自动填充（`seed_data.py` 已废弃）

---

## 实体关系总览

```
Company ──1:N── Product ──1:N── ProductMetric
  │
  ├──1:N── MarketData
  ├──1:N── Financial
  ├──1:N── Forecast
  ├──1:N── CompanyScore
  ├──1:N── Follow                           ← 关注组合
  ├──1:N── PortfolioHolding ──N:1── Portfolio
  │
  ├──1:N── CompanyChainLink ──N:1── IndustryChainLink ──1:N── SupplyDemand
  │
  └──1:N── TimelineEvent
              └── 可选关联: JudgmentLog / IndicatorObservation

KeyIndicator ──1:N── IndicatorObservation

Portfolio ──1:N── PortfolioHolding / PortfolioPerformance / PortfolioEvaluation

ScoringDimension ──1:N── CompanyScore

PriceCache          (独立缓存表)
StockInfoCache      (独立缓存表)
DataSource          (独立配置表)
```

---

## 表定义

### Company（公司）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `name` | String | 公司英文名 |
| `name_cn` | String? | 中文名 |
| `ticker` | String? | 股票代码（NVDA、TSM 等） |
| `sector` | String | 行业分类 |
| `description` | Text? | 公司描述 |
| `logo_url` | String? | Logo 链接 |
| `is_listed` | Boolean | 是否上市 |
| `company_type` | String? | 类型: chip_design / manufacturing / memory / equipment / eda / cloud / llm / application / packaging / networking |
| `revenue_2024` | Float? | 2024 年营收（亿美元） |
| `employee_count` | Integer? | 员工数 |

**关系:** products, market_data, chain_links, financials, forecasts, scores, follows

---

### Product（产品）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `company_id` | FK → companies.id | |
| `name` | String | 产品名 |
| `category` | String | 分类（GPU/AI Accelerator、CPU、Memory 等） |
| `architecture` | String? | 架构（Blackwell、HBM3e 等） |
| `release_date` | Date? | 发布时间 |
| `description` | Text? | 产品描述 |

**关系:** company, metrics

---

### ProductMetric（产品指标）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `product_id` | FK → products.id | |
| `metric_name` | String | 指标名（TDP、memory_bandwidth 等） |
| `metric_value` | Float | 值 |
| `unit` | String | 单位（W、GB/s、TFLOPS 等） |

---

### IndustryChainLink（产业链环节）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `name` | String | 英文名（foundry、memory 等） |
| `name_cn` | String? | 中文名（晶圆制造、存储芯片等） |
| `description` | Text? | 描述 |
| `market_size_2025` | Float? | 2025 市场容量（亿美元） |
| `market_size_2026` | Float? | 2026E |
| `market_size_2027` | Float? | 2027E |
| `growth_rate` | Float? | CAGR % |
| `entry_barriers` | Text? | 进入壁垒 |
| `expansion_difficulty` | String? | 扩产难度（高/中/低） |
| `supply_gap_2025` | String? | 2025 供需缺口描述 |
| `supply_gap_2026` | String? | |
| `supply_gap_2027` | String? | |
| `key_drivers` | Text? | 增长驱动力 |
| `risks` | Text? | 风险 |
| `sort_order` | Integer | 排序 |

---

### CompanyChainLink（公司-环节关联）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `company_id` | FK → companies.id | |
| `chain_link_id` | FK → industry_chain_links.id | |
| `market_share` | Float? | 市场份额 % |
| `revenue_share` | Float? | 收入占比 % |
| `is_leader` | Boolean | 是否龙头 |
| `competitive_advantage` | Text? | 竞争优势 |
| `notes` | Text? | 备注 |

---

### SupplyDemand（供需数据）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `chain_link_id` | FK → industry_chain_links.id | |
| `period` | String | 期间（2025、2026E、2027E） |
| `supply` | Float? | 供应量 |
| `demand` | Float? | 需求量 |
| `unit` | String? | 单位 |
| `gap_pct` | Float? | 缺口百分比（负=短缺） |
| `gap_description` | Text? | 缺口描述 |
| `capacity_utilization` | Float? | 产能利用率 % |
| `lead_time_weeks` | Integer? | 交期（周） |

---

### Financial（公司财务）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `company_id` | FK → companies.id | |
| `fiscal_year` | Integer | 财年 |
| `revenue` | Float? | 营收（亿美元） |
| `revenue_growth` | Float? | 营收增长率 % |
| `net_income` | Float? | 净利润（亿美元） |
| `gross_margin` | Float? | 毛利率 % |
| `operating_margin` | Float? | 营业利润率 % |
| `net_margin` | Float? | 净利率 % |
| `eps` | Float? | 每股收益 |
| `pe` | Float? | PE |
| `pb` | Float? | PB |
| `ps` | Float? | PS |
| `ev_ebitda` | Float? | EV/EBITDA |
| `roe` | Float? | ROE % |
| `debt_equity` | Float? | 负债权益比 |
| `dividend_yield` | Float? | 股息率 % |
| `pe_ttm` | Float? | PE(TTM) |
| `ps_ttm` | Float? | PS(TTM) |

---

### Follow（关注组合）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `company_id` | FK → companies.id | |
| `weight` | Float | 目标权重 % |
| `created_at` | DateTime | |

用于"关注组合"功能，结合 `StockInfoCache` 展示实时价格、多期间收益、EPS/前瞻PE。

---

### KeyIndicator（关键指标）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `name` | String | 英文名 |
| `name_cn` | String? | 中文名 |
| `unit` | String? | 单位 |
| `source` | String? | 数据来源 |
| `source_url` | String? | URL |
| `category` | String? | 分类（对应产业链环节） |
| `description` | Text? | |
| `impact_analysis` | Text? | 影响分析 |
| `is_automated` | Boolean | 是否可自动采集 |
| `update_frequency` | String? | 更新频率 |
| `collection_method` | Text? | 采集方法 |
| `tier` | Integer? | 1=P0核心 2=P1重要 3=P2参考 |
| `related_tickers` | String? | 关联 ticker（逗号分隔） |

---

### IndicatorObservation（指标观测值）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `indicator_id` | FK → key_indicators.id | |
| `date` | Date | |
| `value` | Float | |
| `previous_value` | Float? | 上期值 |
| `change_pct` | Float? | 变化百分比 |
| `note` | Text? | 备注 |
| `data_quality` | String? | 数据质量（confirmed/estimated/preliminary） |
| `analysis` | Text? | AI 生成/人工分析 |

---

### Portfolio（投资组合）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `name` | String | 组合名称 |
| `description` | Text? | 描述 |
| `initial_capital` | Float? | 初始资金 |
| `rebalance_frequency` | String? | 再平衡频率 |
| `strategy_notes` | Text? | 策略说明 |
| `created_at` | DateTime | |

### PortfolioHolding（组合持仓）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `portfolio_id` | FK → portfolios.id | |
| `company_id` | FK → companies.id | |
| `weight` | Float? | 目标权重 % |
| `shares` | Integer? | 持股数 |
| `avg_cost` | Float? | 平均成本 |
| `return_pct` | Float? | 回报率 |

### PortfolioPerformance（组合表现）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `portfolio_id` | FK → portfolios.id | |
| `date` | Date | |
| `total_value` | Float? | 总市值 |
| `cumulative_return` | Float? | 累计收益 |
| `sharpe_ratio` | Float? | 夏普比率 |
| `max_drawdown` | Float? | 最大回撤 |

### PortfolioEvaluation（组合评估）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `portfolio_id` | FK → portfolios.id | |
| `date` | Date | |
| `summary` | Text? | 评估摘要 |
| `adjustment_suggestion` | Text? | 调仓建议 |
| `risk_warnings` | Text? | 风险警告 |
| `conviction_changes` | Text? | 观点变化 |

---

### TimelineEvent（时间线事件）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `event_type` | String | "judgment" / "collection" |
| `event_time` | DateTime | |
| `title` | String | |
| `description` | Text? | |
| `impact_level` | String? | 重大/中等/轻微 |
| `related_tickers` | String? | |
| `related_indicators` | String? | |
| `pre_event_returns` | JSON? | 前 10 日涨跌幅 |
| `post_event_returns` | JSON? | 后 10 日涨跌幅 |
| `source_name` | String? | 采集源 |
| `indicator_name_cn` | String? | |
| `value_display` | String? | |
| `judgment_log_id` | Integer? | FK → judgment_logs |
| `indicator_observation_id` | Integer? | FK → indicator_observations |

---

### JudgmentLog（判断日志）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `date` | Date | 判断日期 |
| `title` | String | 标题 |
| `description` | Text? | 描述 |
| `previous_view` | Text? | 此前判断 |
| `new_view` | Text? | 新判断 |
| `impact_level` | String? | 重大/中等/轻微 |
| `related_companies` | Text? | |
| `related_indicators` | Text? | |
| `evidence` | Text? | 依据 |
| `action_taken` | Text? | 行动 |
| `created_at` | DateTime | |

---

### PriceCache / StockInfoCache

外部数据缓存表：
- **PriceCache**: ticker, date, price, change_pct, volume, source
- **StockInfoCache**: ticker, data_json (完整 JSON), updated_at

---

### DataSource（数据源配置）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `source_name` | String | 数据源名 |
| `source_type` | String | 类型（api/collector/cache） |
| `status` | String | 状态 |
| `last_sync` | DateTime? | 最后同步时间 |
| `config_json` | Text? | 配置信息 |

---

## 索引

关键索引（除 PK 外）:
- `companies.name`, `companies.ticker`
- `products.name`, `market_data.date`, `market_data.company_id`
- `industry_chain_links.name`
- `key_indicators.name`
- `indicator_observations.date`, `indicator_observations.indicator_id`
- `financials.company_id`, `financials.fiscal_year`
- `timeline_events.event_type`, `timeline_events.event_time`
- `price_cache.ticker`, `price_cache.date`
- `stock_info_cache.ticker`
- `follows.company_id`
