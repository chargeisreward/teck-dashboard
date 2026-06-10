# 操作指南

---

## 如何添加一个新的 API 端点

### 步骤

1. **在 `schemas.py` 中定义 Pydantic 模型**

```python
class NewMetricOut(BaseModel):
    id: int
    name: str
    value: float
    model_config = {"from_attributes": True}
```

2. **在 `main.py` 中添加端点函数**

```python
@app.get("/api/new-metrics", response_model=list[NewMetricOut])
def list_new_metrics(db: Session = Depends(get_db)):
    items = db.query(NewMetric).all()
    return items
```

3. **在 `api.js` 中添加前端 API 函数**

```javascript
export function getNewMetrics() {
  return fetchJSON(`${API_BASE}/new-metrics`);
}
```

4. **在前端页面中调用**

```javascript
const [metrics, setMetrics] = useState([]);
useEffect(() => { getNewMetrics().then(setMetrics); }, []);
```

### 最佳实践

- 使用 `response_model` 确保响应类型安全
- 数据库查询使用 SQLAlchemy ORM，不要裸 SQL
- 错误通过 HTTPException + 状态码返回
- 前端 `api.js` 中的函数统一使用 `fetchJSON` 包装异常处理

---

## 如何添加一个新的数据源

`price_data.py` 的数据源采用模块化设计，每种数据源是一个独立的 `_fetch_*` 函数。

### 步骤

1. **实现获取函数**

```python
def _fetch_new_source(ticker: str, days: int) -> list[dict]:
    """从新数据源获取历史价格"""
    # 必须返回 [{"date": "2024-01-01", "price": 150.0, "change_pct": 0.5, "volume": 1000000, "source": "new_source"}, ...]
    pass
```

2. **注册 ticker 映射**

```python
NEW_SOURCE_MAP = {
    "SOME_TICKER": "new_source_code",
}
```

3. **在 `fetch_price_history()` 中添加调用链**

```python
# 在你的数据源优先级位置插入
if clean_ticker in NEW_SOURCE_MAP:
    result = _fetch_new_source(clean_ticker, days)
    if result:
        return result
```

4. **同样的模式加入 `get_stock_info()` 和 `get_current_price()`**

### 数据源契约

每个 `_fetch_*` 函数必须：
- 异常安全（内部 try/except，失败返回空列表/None）
- 返回统一格式的 dict 列表
- 不阻塞主流程（超时设置 ≤ 10s）
- 不修改数据库（由调用方 `get_price_history_cached()` 处理缓存）

---

## 如何配置一个新的行业数据采集器

采集器位于 `backend/industry_collector/` 下，每个文件是一个独立模块。

### 步骤

1. **创建采集模块** `backend/industry_collector/my_source.py`

```python
"""我的数据源采集器"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)
SOURCE_NAME = "my_source"

def collect() -> list[dict]:
    """执行采集，返回指标观测值列表

    Returns:
        [{"indicator_name": "my_indicator",
          "date": "2026-06-11",
          "value": 123.4,
          "change_pct": 2.5,
          "note": "optional note"}, ...]
    """
    try:
        # 采集逻辑...
        return results
    except Exception as e:
        logger.error(f"my_source collect failed: {e}")
        return []
```

2. **在 `main.py` 中注册**

在 `collector_map` 字典中添加：
```python
from industry_collector import my_source
collector_map = {
    # ... 现有 ...
    "my_source": my_source,
}
```

3. **在 `seed_data.py` 中创建对应指标**

在 `seed_key_indicators()` 中添加：
```python
db.add(KeyIndicator(
    name="my_indicator", name_cn="我的指标",
    category="foundry", unit="%", source="My Source",
    is_automated=True, update_frequency="周度",
    tier=2, related_tickers="NVDA,TSM",
))
```

4. **触发采集验证**

```bash
curl -X POST "http://localhost:8001/api/industry/collect?source=my_source"
```

---

## 如何创建自定义估值场景

### 使用估值 API

**v1 Gordon Growth 场景：**

```bash
curl -X POST "http://localhost:8001/api/valuation/calculate" \
  -H "Content-Type: application/json" \
  -d '{
    "peer_group": "gpu_ai",
    "revenue_growth": 25.0,
    "net_margin": 40.0,
    "discount_rate": 12.0,
    "terminal_growth": 3.0,
    "growth_years": 5,
    "china_premium": 2.0
  }'
```

参数含义：
- `revenue_growth`: 假设的未来 5 年营收年增长率
- `net_margin`: 稳态净利率（null = 使用当前值）
- `discount_rate`: WACC/折现率，越高估值越低
- `china_premium`: 中国公司国产替代溢价，加在增长率上

**v2 供需感知未来PE场景：**

```bash
curl -X POST "http://localhost:8001/api/valuation-v2/calculate" \
  -H "Content-Type: application/json" \
  -d '{
    "peer_group": "memory",
    "growth_years": 5,
    "revenue_growth": null,
    "net_margin": null,
    "use_supply_demand": true
  }'
```

参数含义：
- `revenue_growth`: null = 使用系统推荐值（分析师→CAGR→链级增长率）
- `use_supply_demand`: true = 启用供需分数调整增长假设

### 可用的 peer_group 值

`gpu_ai`, `memory`, `foundry`, `equipment`, `eda_ip`, `packaging`, `cloud`, `llm_ai`, `application`, `networking`, `other`

---

## 如何添加新公司到数据库

### 使用 seed_data.py

1. 在 `seed_companies()` 函数中添加：

```python
db.add(Company(
    name="New Company Inc.",
    name_cn="新公司",
    ticker="NEWC",
    sector="Semiconductor",
    company_type="chip_design",
    is_listed=True,
    revenue_2024=10.5,
    employee_count=5000,
))
db.flush()  # 获取 ID
```

2. 添加到产业链环节：

```python
db.add(CompanyChainLink(
    company_id=new_company_id,
    chain_link_id=foundry_link_id,  # 从 IndustryChainLink 查询
    market_share=2.5,
    is_leader=False,
    competitive_advantage="差异化技术",
))
```

3. 添加财务数据：

```python
db.add(Financial(
    company_id=new_company_id,
    fiscal_year=2025,
    revenue=10.5,
    revenue_growth=15.0,
    net_income=2.1,
    net_margin=20.0,
))
```

4. 重新运行 `python seed_data.py`（注意：可能需要先清空数据或使用 upsert 逻辑）

### 注意事项

- `company_type` 必须使用枚举值：`chip_design` / `manufacturing` / `memory` / `equipment` / `eda` / `cloud` / `llm` / `application` / `packaging` / `networking`
- `ticker` 对于未上市公司为 null
- 需要同时在 `price_data.py` 的 `TENCENT_US_MAP` / `TENCENT_KLINE_MAP` 中添加 ticker 映射才能显示实时价格

---

## 如何记录一个判断变化

### 通过 API

```bash
curl -X POST "http://localhost:8001/api/judgment-logs" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-06-11",
    "title": "HBM4 提前量产",
    "description": "SK海力士宣布 HBM4 将提前至 2026Q3 量产",
    "previous_view": "预计 2027 年量产",
    "new_view": "2026Q3 量产提前一季",
    "impact_level": "重大",
    "related_companies": "000660,MU",
    "related_indicators": "hbm_price,hbm_bandwidth"
  }'
```

### 通过前端

在"产业情报"页面点击 **+ 新增判断** 按钮，填写表单并保存。

### 后续影响

记录会自动出现在时间线中。系统会：
1. 自动计算关联 ticker 的前后 10 日涨跌幅
2. 在时间线中显示
3. 前端 `IndustryIntelligence` 页面自动刷新

---

## 如何设置一个新的投资组合

### 通过种子数据

在 `seed_data.py` 中添加：

```python
portfolio = Portfolio(
    name="AI芯片精选组合",
    description="AI芯片全产业链配置",
    initial_capital=1000000.0,
    rebalance_frequency="monthly",
    strategy_notes="聚焦AI算力和存储",
)
db.add(portfolio)
db.flush()

holdings = [
    PortfolioHolding(portfolio_id=portfolio.id, company_id=nvda_id, weight=30.0),
    PortfolioHolding(portfolio_id=portfolio.id, company_id=tsm_id, weight=25.0),
    PortfolioHolding(portfolio_id=portfolio.id, company_id=skhynix_id, weight=20.0),
]
for h in holdings:
    db.add(h)
```

### 后续

- 系统自动跟踪组合表现（通过 `scheduler.py` 定时更新）
- 通过 `POST /api/portfolios/{id}/evaluate` 获取 AI 调仓建议
- 前端"模拟组合"页面显示全部指标

---

## 如何排查常见问题

### 后端启动失败

```bash
# 检查端口占用
lsof -i :8001
# 检查数据库文件
ls -l backend/teck_dashboard.db
# 重新初始化
cd backend && python seed_data.py
```

### 价格数据为空

1. 检查 `price_data.py` 中的 ticker 映射
2. 腾讯财经 API 需要正确的交易所后缀（.N / .OQ / .AM）
3. 查看 `backend/server.log` 中是否有 API 限流日志
4. 韩国股票检查 Naver API 返回值

### akshare 连接失败

```bash
# 检查网络
pip install akshare --upgrade
# akshare 依赖 cninfo 等源，可能需要国内网络环境
```

### DeepSeek AI 分析不生成

检查 `ai_analysis.py` 中的 API Key 是否有效：
```bash
curl https://api.deepseek.com/v1/chat/completions \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-chat", "messages": [{"role": "user", "content": "test"}]}'
```
