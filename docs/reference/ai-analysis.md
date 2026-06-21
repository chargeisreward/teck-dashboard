# AI 分析模块参考

`backend/ai_analysis.py` 负责调用大语言模型，为产业指标生成两类文本：

- `analysis`：一句话边际变化分析（50–80 字），解释指标变化的驱动逻辑与产业链含义。
- `industry_impact` / `chain_impact` / `company_impact`：三重影响分析，分别说明对行业景气度、产业链环节、重点公司的影响。

当前默认使用 MiniMax OpenAI-compatible API，模型 `MiniMax-M3`。

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `MINIMAX_API_KEY` | 是 | — | MiniMax API 鉴权密钥 |
| `MINIMAX_BASE_URL` | 否 | `https://api.minimax.io/v1` | MiniMax API 基础地址 |
| `MINIMAX_MODEL` | 否 | `MiniMax-M3` | 模型 ID |

本地开发时将这些变量写入项目根目录 `.env`（已 gitignore）。生产环境通过 Zeabur Dashboard 设置。

## 公共函数

### `generate_indicator_analysis(...) -> str | None`

为单个指标观测值生成一句话分析。

参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| `name_cn` | `str` | 指标中文名 |
| `category_cn` | `str` | 供应链环节中文名 |
| `latest_value` | `float` | 最新观测值 |
| `previous_value` | `float \| None` | 上一期观测值 |
| `change_pct` | `float \| None` | 环比变化百分比 |
| `unit` | `str` | 单位 |
| `source` | `str` | 数据来源 |

行为：

- 当 `change_pct` 为 `None` 时直接返回 `None`。
- 使用内存缓存，键为 `{name_cn}:{latest_value}:{change_pct}`，避免同一指标同一数值重复调用 API。
- 调用 MiniMax 时 `max_tokens=2000`、`temperature=0.3`。
- 返回结果会去除首尾引号后写入缓存；调用方通常将其持久化到 `IndicatorObservation.analysis`。

### `generate_industry_impact_analysis(...) -> dict | None`

生成三重影响分析 JSON。

参数额外包含：

| 参数 | 类型 | 说明 |
|---|---|---|
| `marginal_change_pct` | `float \| None` | 边际变化百分比 |
| `comparison_window` | `str \| None` | 边际变化窗口描述，如 `30d` |
| `related_tickers` | `str` | 关联公司 ticker 列表，逗号分隔 |

返回格式：

```json
{
  "industry_impact": "对行业整体景气度的影响...",
  "chain_impact": "对产业链各环节的影响...",
  "company_impact": "对重点公司估值的正面/负面影响..."
}
```

行为：

- 当 `change_pct` 与 `marginal_change_pct` 都为 `None` 时返回 `None`。
- 使用 `response_format={"type": "json_object"}` 要求模型输出 JSON。
- `max_tokens=2500`，为模型留出足够的 thinking token。
- 返回内容先经 `_strip_json_fences` 去除 Markdown 围栏，再 `json.loads`。

### `_call_minimax(prompt, max_tokens=400, temperature=0.3, response_format=None, timeout=40) -> str | None`

底层 HTTP 调用封装。使用 `requests.post` 访问 `{MINIMAX_BASE_URL}/chat/completions`，Bearer 鉴权。

### `_strip_thinking(content: str) -> str`

去除 MiniMax-M3 输出的 `<think>...</think>` 与 `<thinking>...</thinking>` 推理块。

### `_strip_json_fences(content: str) -> str`

去除 Markdown JSON 代码围栏（` ```json ... ``` `）。

### `clear_cache()`

清空模块级内存缓存，主要用于测试。

## 响应清洗流程

MiniMax-M3 会返回两类需要清洗的内容：

1. `<think>` 推理块：包含模型内部推理，不应暴露给用户。
2. Markdown JSON 围栏：当要求 JSON 输出时，模型可能用 ` ```json ... ``` ` 包裹。

因此 `_call_minimax` 先调用 `_strip_thinking`；`generate_industry_impact_analysis` 在 JSON 解析前再调用 `_strip_json_fences`。

## 批量调用与后台任务

`backend/main.py` 中的 `batch_analyze_industry_impact(db, limit=20)` 会扫描所有缺少 `industry_impact` 或 `analysis` 的最新 `IndicatorObservation`，依次调用上述两个函数，并将结果写回数据库。

为避免在 Zeabur 等 PaaS 上触发请求超时，`POST /api/industry/batch-analyze` 使用 FastAPI `BackgroundTasks` + `asyncio.to_thread`：

- HTTP 请求立即返回 `{success: true, message: "后台批量分析已启动，每次最多处理 3 条观测值"}`。
- 实际工作在后台线程中执行，每次最多处理 3 条观测值。

APScheduler 每日 6:00 与 18:00 自动调用 `batch_analyze_industry_impact`。

## 错误处理

- 若 `MINIMAX_API_KEY` 未设置，函数直接返回 `None` 并记录 warning。
- HTTP 非 200 或解析失败时返回 `None`，不会抛异常影响主流程。
- 调用方应检查返回值并在前端提供兜底文案。

## 相关

- [切换 AI 分析提供商](../how-to/switch-ai-provider.md)
- [为什么使用 MiniMax-M3](../explanation/ai-analysis-provider.md)
- [产业情报统一视图设计](../explanation/industry-intelligence-view.md)
- [配置参考](configuration.md)
