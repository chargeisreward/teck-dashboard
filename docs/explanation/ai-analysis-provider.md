# 为什么 AI 分析使用 MiniMax-M3

## 背景

项目早期使用 DeepSeek API 为指标边际变化生成一句话分析。2026-06 月，DeepSeek 提供的 Coding Agent 专用接口对通用 HTTP 客户端返回 403，无法继续作为后端分析服务使用。我们需要一个 OpenAI-compatible、支持中文、且能被普通 HTTP 调用访问的替代方案。

## 选型过程

1. **Kimi Code**：尝试后发现其 API 仅限 Coding Agents 调用，普通后端服务返回 `403 Forbidden`。
2. **MiniMax Code / MiniMax-M3**：提供标准 OpenAI-compatible Chat Completions 接口，普通 Bearer Token 即可调用；中文输出质量满足 50–80 字分析需求。
3. **自托管/其他**：未引入，因为 MiniMax 已满足需求且无需额外运维。

最终切换到 **MiniMax-M3**。

## 关键适配

### Thinking token 占用输出长度

MiniMax-M3 会把推理过程放在 `<think>...</think>` 块里，这部分同样消耗 `max_tokens`。最初使用 `max_tokens=200` 时，模型只输出了 thinking 块，没有真正答案。因此：

- 一句话分析：`max_tokens=2000`
- JSON 三重影响分析：`max_tokens=2500`

### Markdown JSON 围栏

要求 `response_format={"type": "json_object"}` 后，模型仍可能返回 ` ```json ... ``` `。我们在解析前用 `_strip_json_fences` 去除。

### 后台化避免超时

同步调用 20 条观测值会超出 Zeabur 网关超时，导致 502。因此 `/api/industry/batch-analyze` 改为 FastAPI BackgroundTask，并在后台线程中每次只处理 3 条。

## 设计取舍

| 权衡点 | 选择 | 代价 |
|---|---|---|
| 模型能力 vs 成本 | MiniMax-M3 | 输出需清洗 thinking/围栏 |
| 实时生成 vs 成本控制 | 首次生成后写入 DB 缓存 | 新数据到达后不会立刻有分析，需等调度或手动触发 batch-analyze |
| 批量处理 vs 超时 | 后台任务 + 每次 3 条 | 全部指标分析完需要多个周期 |
| 容错 | 失败返回 `None` | 前端需准备兜底文案 |

## 替代方案

- **实时调用**：每次 GET `/api/industry-intelligence` 都调 AI。弃用，因为成本高且可能阻塞。
- **只生成 P0 指标**：减少调用量。弃用，因为 P1/P2 指标也需要判断逻辑。
- **本地小模型**：减少外部依赖。弃用，因为本地模型对中文金融分析质量不稳定，且增加部署复杂度。

## 运维影响

- 环境变量从 `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` 改为 `MINIMAX_API_KEY` / `MINIMAX_BASE_URL` / `MINIMAX_MODEL`。
- Zeabur 部署时需要删除旧变量、设置新变量，然后 `zeabur service redeploy`。
- 日志与文档中逐步替换 DeepSeek 引用。

## 相关

- [AI 分析模块参考](../reference/ai-analysis.md)
- [如何切换 AI 分析提供商](../how-to/switch-ai-provider.md)
- [配置参考](../reference/configuration.md)
