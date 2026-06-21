# 如何切换 AI 分析服务提供商

本指南说明如何将后端的 AI 分析从一个提供商切换到另一个（例如从 DeepSeek 切换到 MiniMax），并在本地和 Zeabur 上验证。

## 前置条件

- 新的 AI 提供商账号与 API Key。
- 新提供商支持 OpenAI-compatible Chat Completions 接口（或你愿意修改 `backend/ai_analysis.py`）。
- 本地能启动后端：`cd backend && uvicorn main:app --reload --port 8001`。
- Zeabur CLI 已登录并指向正确项目。

## 步骤

### 1. 修改 `backend/ai_analysis.py`

更新环境变量读取：

```python
NEW_API_KEY = os.getenv("NEW_API_KEY", "")
NEW_BASE_URL = os.getenv("NEW_BASE_URL", "https://api.new-provider.com/v1")
NEW_MODEL = os.getenv("NEW_MODEL", "new-model-id")
```

如果新模型输出 reasoning 块或 Markdown JSON 围栏，添加/更新清洗函数，例如 `_strip_thinking` 和 `_strip_json_fences`。

### 2. 调整 token 预算

测试新模型的一句话分析和 JSON 分析所需的最小 `max_tokens`：

```bash
python -c "from ai_analysis import generate_indicator_analysis; print(generate_indicator_analysis('TSMC月度营收','晶圆制造',4169.75,3724.50,12.0,'亿NT$','tsmc_ir'))"
```

如果输出为空或只包含 thinking 块，逐步提高 `max_tokens`。

### 3. 更新 `.env.example`

```bash
NEW_API_KEY=your-new-api-key-here
NEW_BASE_URL=https://api.new-provider.com/v1
NEW_MODEL=new-model-id
```

### 4. 本地测试

```bash
cd backend
# 设置环境变量
export NEW_API_KEY=your-new-api-key-here
export NEW_BASE_URL=https://api.new-provider.com/v1
export NEW_MODEL=new-model-id

# 测试两个生成函数
python -c "from ai_analysis import generate_indicator_analysis, generate_industry_impact_analysis; ..."
```

确认返回中文文本或 JSON，且无 thinking 块残留。

### 5. 提交代码（不要提交 key）

```bash
git add backend/ai_analysis.py .env.example docs/reference/configuration.md
git commit -m "docs: switch AI provider to ..."
```

确保 `.env` 仍在 `.gitignore` 中。

### 6. 更新 Zeabur 环境变量

```bash
# 删除旧变量
zeabur variable env delete DEEPSEEK_API_KEY --id <service-id>
zeabur variable env delete DEEPSEEK_BASE_URL --id <service-id>

# 添加新变量
zeabur variable env set NEW_API_KEY your-new-api-key-here --id <service-id>
zeabur variable env set NEW_BASE_URL https://api.new-provider.com/v1 --id <service-id>
zeabur variable env set NEW_MODEL new-model-id --id <service-id>
```

本项目真实 service ID 见 [[teck-dashboard-zeabur-config]]（`service-6a2ab73e4a7ea31c689a1258`）。

### 7. 重新部署

因为 service 类型是 `PREBUILT_V2`，git push 不会自动 rebuild：

```bash
zeabur service redeploy --id 6a2ab73e4a7ea31c689a1258 --env-id 6a2ab4be05a35017ba906658 -y
```

### 8. 线上验证

```bash
curl https://sacs.zeabur.app/api/dashboard/overview
curl https://sacs.zeabur.app/api/industry-intelligence
curl -X POST https://sacs.zeabur.app/api/industry/batch-analyze
```

过几分钟后再次 GET `/api/industry-intelligence`，确认 `analysis` / `industry_impact` 字段已填充。

## 常见问题

### 线上 502 / 超时

如果 `/api/industry/batch-analyze` 同步调用多条观测值导致超时，改为 FastAPI `BackgroundTasks`：

```python
from fastapi import BackgroundTasks
import asyncio

async def _batch_analyze_worker():
    def _run():
        db = SessionLocal()
        try:
            batch_analyze_industry_impact(db, limit=3)
        finally:
            db.close()
    await asyncio.to_thread(_run)

@app.post("/api/industry/batch-analyze")
async def trigger_batch_analyze(background_tasks: BackgroundTasks):
    background_tasks.add_task(_batch_analyze_worker)
    return {"success": True, "message": "后台批量分析已启动"}
```

### 输出包含 `<think>` 或 ` ```json `

在解析前添加清洗函数（见 `ai_analysis.py` 的 `_strip_thinking` 和 `_strip_json_fences`）。

### API Key 泄露检查

```bash
git log --all --source -S 'sk-' -- backend/ai_analysis.py .env
```

如发现历史提交包含 key，立即轮换 key 并重写历史。

## 相关

- [AI 分析模块参考](../reference/ai-analysis.md)
- [为什么使用 MiniMax-M3](../explanation/ai-analysis-provider.md)
- [配置参考](../reference/configuration.md)
- [[teck-dashboard-zeabur-config]] — 真实 service/domain/env 配置
