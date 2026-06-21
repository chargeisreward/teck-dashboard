# AI 芯片与半导体存储产业链分析仪表盘

> 技术文档 — 基于 Diataxis 框架

---

## 入门

如果你是第一次接触这个项目：

| 文档 | 适合谁 | 内容 |
|------|--------|------|
| [教程](tutorial.md) | 新用户 | 从零启动仪表盘，探索功能 |
| [架构概览](explanation/architecture.md) | 开发者 | 系统整体设计 |

## 操作指南

如果你有具体任务要完成：

| 文档 | 内容 |
|------|------|
| [操作指南合集](how-to/index.md) | 添加API端点、数据源、公司、估值场景等 |
| [部署到 Zeabur](how-to/deploy.md) | Docker 构建、环境变量、持久卷配置 |
| [切换 AI 分析提供商](how-to/switch-ai-provider.md) | 更换 AI 服务、本地测试、Zeabur 更新 |
| [如何排查常见问题](how-to/index.md#如何排查常见问题) | 启动失败、数据为空、API 限流 |

## 参考

如果你需要查找具体信息：

| 文档 | 内容 |
|------|------|
| [API 参考](reference/api.md) | 全部 59 端点详细说明 |
| [数据库参考](reference/database.md) | 24 数据表结构、关系、索引 |
| [前端参考](reference/frontend.md) | 13 页面组件树、路由、API 客户端模式 |
| [配置参考](reference/configuration.md) | 全部环境变量、Docker 构建参数 |
| [AI 分析模块参考](reference/ai-analysis.md) | MiniMax 接口、函数、响应清洗、后台任务 |

## 概念解读

如果你想深入理解设计原理：

| 文档 | 内容 |
|------|------|
| [估值方法论](explanation/valuation.md) | Gordon Growth v1 + 供需感知 Future PE v2 |
| [数据源策略](explanation/data-sources.md) | 多数据源切换、14 采集器、宏观指标、缓存机制 |
| [行情数据策略](explanation/price-data-strategy.md) | 腾讯/yfinance/akshare/Naver 优先级与降级 |
| [产业情报统一视图](explanation/industry-intelligence-view.md) | P0/P1/P2 分层、时间线事件总线、AI 分析 |
| [为什么使用 MiniMax-M3](explanation/ai-analysis-provider.md) | AI 提供商切换的设计 rationale |

## 专题文档

| 文档 | 内容 |
|------|------|
| [数据获取全览](../data_get.md) | 全部数据获取方式、API Key 管理、14 采集器、宏观数据、调度配置 |

---

## 快速链接

- 后端 API 文档: `http://localhost:8001/docs`
- 前端地址: `http://localhost:5173`
- 项目仓库: `D:\cha_code_project\Teck dashboard for AI chips semiconductor storage`
