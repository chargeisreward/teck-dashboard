# API 参考

> 基础路径: `/api`。所有请求通过 FastAPI 提供，自动生成 OpenAPI 文档于 `/docs`。
> 端口: `8001`。前端开发模式下 Vite 代理 `/api` → `localhost:8001`。

---

## 仪表盘

### `GET /api/dashboard/summary`

市场概览统计。

**响应:**
```json
{
  "total_companies": 42,
  "total_products": 156,
  "total_storage_products": 28,
  "latest_market_caps": [
    {"ticker": "NVDA", "name": "NVIDIA", "market_cap": 2800000000000}
  ],
  "product_categories": [
    {"category": "GPU/AI Accelerator", "count": 12}
  ]
}
```

---

## 公司

### `GET /api/companies`

所有公司列表。

### `GET /api/companies/{id}`

公司详情（含产品、市场数据）。

### `GET /api/companies/{id}/financials`

公司年度财务数据（营收、净利润、PE、PB、ROE 等）。

### `GET /api/companies/{id}/forecasts`

公司预测数据（分析师一致预期）。

### `GET /api/stock/{ticker}`

指定 ticker 的完整股票信息（多源获取，含实时价、PE、市值等）。

---

## 产业链

### `GET /api/chain-links`

所有产业链环节列表。

### `GET /api/chain-links/{id}`

单个环节详情（含市场容量、供需数据）。

### `GET /api/chain-links/{id}/companies`

某环节关联的公司列表（含市占率、竞争优势）。

### `GET /api/industry-overview`

全产业链概览（嵌套的环节 + 公司 + 供需数据）。产业链全景页面的核心数据源。

### `GET /api/supply-demand?chain_link_id=&period=`

供需分析数据。筛选参数可选。

---

## 产品

### `GET /api/products?category=`

产品列表，按类别筛选（可选）。

### `GET /api/categories`

产品类别列表。

### `GET /api/storage?storage_type=`

存储产品列表，按类型筛选（可选）。

---

## 行情与市场

### `GET /api/market-data?company_id=&days=90`

市场数据（股价），按公司筛选（可选），天数可选（默认 90 日）。

### `GET /api/price/{ticker}?days=90`

指定 ticker 的价格历史。多数据源自动切换（腾讯→yfinance→akshare）。

### `GET /api/stock-info/{ticker}`

指定 ticker 的股票信息（市值、PE、PS、PB 等）。

### `GET /api/price/smart/{company_name}?days=90`

智能定价查询。`company_name` 为 URL 编码的中文/英文名。

### `GET /api/market/hot-stocks`

A 股涨跌榜（`akshare stock_zh_a_spot_em()`）。

---

## 关键指标

### `GET /api/indicators?category=`

指标列表。按类别筛选（可选）。

### `GET /api/indicator-categories`

指标类别列表。

### `GET /api/indicators/{id}`

单指标详情。

### `GET /api/indicators/{id}/observations?limit=90`

指标观测值序列（最新 N 条）。

---

## 产业数据

### `GET /api/industry/indicators?category=&source=`

产业指标列表。可选按类别/数据源筛选。

### `GET /api/industry/indicators/{id}`

产业指标详情。

### `POST /api/industry/collect?source=`

触发指定数据源的采集。返回采集结果。

### `GET /api/industry/data-sources`

所有数据源及其状态。

### `GET /api/industry/refresh`

触发全量数据采集（所有采集器运行 + 产业链数据 + MarketData 同步）。返回采集统计。

---

## 产业情报（统一接口）

### `GET /api/industry-intelligence`

返回产业情报聚合数据，包含：

```json
{
  "indicators": [
    {
      "id": 1, "name": "tsmc_revenue", "name_cn": "台积电月营收",
      "category": "foundry", "tier": 1,
      "latest_value": 416900000000, "unit": "TWD",
      "change_pct": 2.3, "latest_date": "2026-05-31",
      "update_frequency": "月度", "source": "TSMC IR",
      "source_url": "https://...",
      "analysis": "AI 驱动先进制程需求持续旺盛...",
      "related_tickers": "TSM,NVDA,AMD",
      "pre_event_returns": {"NVDA": {"abs": 2.1, "rel": 1.5}, "SOX": {"abs": 0.6}},
      "post_event_returns": {"NVDA": {"abs": 3.2, "rel": 2.0}, "SOX": {"abs": 1.2}}
    }
  ],
  "timeline": [...],
  "data_sources": [{"source": "tsmc_ir", "status": "ok"}],
  "stats": {
    "total_indicators": 85, "with_data": 62,
    "tier1_count": 12, "tier2_count": 28, "tier3_count": 45
  }
}
```

---

## 时间线

### `GET /api/timeline?limit=50&offset=0&event_type=`

时间线事件列表。支持分页和按事件类型筛选（judgment / collection）。

### `POST /api/timeline/{event_id}/refresh-returns`

刷新单个时间线事件的关联证券涨跌幅。

### `POST /api/timeline/refresh-pending`

刷新所有待更新的事件后涨跌幅。

---

## 判断日志

### `GET /api/judgment-logs`

所有判断记录。

### `POST /api/judgment-logs`

创建新判断记录。

**请求体:**
```json
{
  "date": "2026-06-11",
  "title": "HBM3e 供应趋紧",
  "description": "SK海力士HBM3e产能已被预订一空",
  "impact_level": "重大",
  "previous_view": "预计2026H2供需平衡",
  "new_view": "全年供应紧张",
  "related_companies": "000660,MU",
  "related_indicators": "hbm_price",
  "evidence": "2026Q1 conference call",
  "action_taken": "上调SK海力士目标价"
}
```

---

## 关注组合

### `GET /api/user/follows`

返回所有关注公司的实时数据（ticker、价格、PE_TTM、市值、当日涨跌幅、各期间收益等）。

### `POST /api/user/follow/refresh-prices`

批量刷新所有关注公司的实时价格（调用腾讯 API + 写入 StockInfoCache）。

---

## 投资组合

### `GET /api/portfolios`

所有组合列表。

### `GET /api/portfolios/{id}`

组合详情（含持仓、表现、评价）。

### `GET /api/portfolios/{id}/holdings`

组合持仓详情。

### `GET /api/portfolios/{id}/performance?limit=60`

组合历史表现（日收益率、累计收益、夏普比率、最大回撤）。

### `GET /api/portfolios/{id}/evaluations`

组合评价历史。

### `POST /api/portfolios/{id}/evaluate`

触发组合 AI 评估。返回评估建议。

### `GET /api/portfolio/tracking`

组合完整跟踪数据，包含：
- 每只持仓的实时价、涨跌幅、PE_TTM
- 7 段期间涨跌幅（1日/1周/1月/3月/6月/1年/3年）
- EPS_TTM、EPS 增速、2026E/2027E EPS、前瞻 PE
- 组合级加权汇总（加权 PE、加权 EPS、加权各期间收益）

### `PUT /api/portfolio/weight/{follow_id}`

更新单个持仓的关注权重。

**请求体:** `{"weight": 25.0}`

### `POST /api/portfolio/rebalance`

按最新权重和价格重算组合仓位。

### `POST /api/portfolio/seed`

手动播种默认组合（AI Chip Core Portfolio）。

---

## 评分系统

### `GET /api/scoring/dimensions`

评分维度定义（如：技术壁垒、成长性、估值等）。

### `GET /api/scoring/scores`

所有公司评分汇总（含各维度分项和总分）。

---

## 估值模型 v1 (Gordon Growth)

### `GET /api/valuation/peer-groups`

估值同群组定义列表。

### `GET /api/valuation/companies?peer_group=memory`

获取群组内公司数据（财务、估值输入）。

### `POST /api/valuation/calculate`

执行估值计算。

**请求体:**
```json
{
  "peer_group": "memory",
  "revenue_growth": 20.0,
  "net_margin": null,
  "discount_rate": 10.0,
  "terminal_growth": 3.0,
  "growth_years": 5,
  "china_premium": 0.0
}
```

**响应:** 群组内每家公司的公允PE、公允市值、上涨空间、隐含增长率、成对 breakeven 矩阵。

---

## 估值模型 v2 (供需感知未来PE)

### `GET /api/valuation-v2/chain-scores`

所有产业链环节的供需量化分数。

### `GET /api/valuation-v2/company-adjustments?peer_group=memory`

公司推荐调整参数（推荐增长率、推荐净利率）。

### `POST /api/valuation-v2/calculate`

执行未来 PE 估值计算。

**请求体:**
```json
{
  "peer_group": "memory",
  "growth_years": 5,
  "revenue_growth": null,
  "net_margin": null,
  "use_supply_demand": true
}
```

**响应:** 每家公司的未来 PE、基准 PE、估值信号（低估/合理/高估）。
