# 操作指南

---

| 指南 | 内容 |
|------|------|
| [部署到 Zeabur](deploy.md) | Docker 构建、环境变量、持久卷配置 |
| [如何排查常见问题](#如何排查常见问题) | 启动失败、数据为空、API 限流 |

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

所有采集器位于 `backend/industry_collector/` 下，继承 `BaseCollector` 类。

### 步骤

1. **创建采集器类** `backend/industry_collector/sources/my_source.py`

```python
"""我的数据源采集器"""
import logging
from datetime import datetime
from industry_collector.base import BaseCollector

logger = logging.getLogger(__name__)

class MySourceCollector(BaseCollector):
    source = "my_source"
    indicator_name = "my_indicator"
    indicator_name_cn = "我的指标"
    unit = "%"
    category = "foundry"
    category_cn = "晶圆制造"
    update_frequency = "monthly"
    description = "指标描述"
    source_url = "https://..."
    collection_method = "网页爬虫"

    async def collect(self, db=None) -> dict:
        # 采集逻辑...
        # 调用 self._write_observation(db, indicator_id, value) 写入数据
        return {"success": True, "value": value, ...}
```

2. **在 `__init__.py` 中注册**

```python
from .sources.my_source import MySourceCollector

COLLECTORS["my_source"] = [MySourceCollector]
```

3. **触发采集验证**

```bash
curl -X POST "http://localhost:8001/api/industry/collect?source=my_source"
```

---

## 如何添加新公司到数据库

### 方法一：通过启动迁移（适合部署环境）

修改 `backend/startup_migration.py` 中的 `TICKERS_TO_ENSURE` 字典：

```python
TICKERS_TO_ENSURE = {
    "NEWC": {
        "name": "New Company",
        "name_cn": "新公司",
        "sector": "NAND Flash",
        "company_type": "memory",
        "is_listed": True,
        "description": "...",
        "chain_link_id": 3,       # IndustryChainLink ID
        "follow_weight": 20.0,    # 关注组合权重
    },
}
```

重启后端服务即可自动补入。

### 方法二：使用 seed_data.py（本地开发）

在 `seed_companies()` 函数中添加：

```python
db.add(Company(
    name="New Company Inc.",
    name_cn="新公司",
    ticker="NEWC",
    sector="Semiconductor",
    company_type="chip_design",
    is_listed=True,
))
db.flush()
```

### 后续步骤

添加公司后还需：
1. **添加到产业链环节**：`CompanyChainLink` 表
2. **添加到实时行情映射**：`price_data.py` 的 `TENCENT_US_MAP` 和 `TENCENT_KLINE_MAP`
3. **添加到前端颜色**：`frontend/src/pages/PortfolioPage.jsx` 的 `TICKER_COLORS`
4. **运行 `backfill_3y_prices.py`**：补齐历史价格数据

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

## 如何排查常见问题

### 后端启动失败

```bash
# 检查端口占用
lsof -i :8001
# 检查数据库文件
ls -l backend/teck_dashboard.db
# 检查启动迁移日志
tail -20 backend/server.log | grep -i "startup"
```

### 价格数据为空

1. 检查 `price_data.py` 中的 ticker 映射（`TENCENT_US_MAP` / `TENCENT_KLINE_MAP`）
2. 腾讯财经 API 需要正确的交易所后缀（.N / .OQ / .AM）
3. 查看 `backend/server.log` 中是否有 API 限流日志
4. 韩国股票检查 Naver API 返回值
5. 运行 `python backfill_3y_prices.py` 回填历史数据

### akshare 连接失败

```bash
# 检查网络
pip install akshare --upgrade
# akshare 依赖国内数据源，可能需要国内网络环境
```

### DeepSeek AI 分析不生成

检查 `ai_analysis.py` 中的 API Key 是否有效：
```bash
curl https://api.deepseek.com/v1/chat/completions \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-chat", "messages": [{"role": "user", "content": "test"}]}'
```

### 组合跟踪页面无数据

1. 检查 `Follow` 表是否有记录：`GET /api/user/follows`
2. 检查 `PriceCache` 表是否有日频数据
3. 检查 `StockInfoCache` 是否有 `current_price` 和 `pe_ttm`
4. 运行 `python backfill_3y_prices.py` 补齐历史价格
