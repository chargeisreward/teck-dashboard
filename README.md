# AI 芯片与半导体存储产业链分析仪表盘

AI 芯片与半导体产业链深度分析平台。覆盖 42+ 上市公司、10+ 产业链环节、多数据源行情、两代估值模型、14 个行业数据采集器。

## 功能概览

| 模块 | 描述 |
|------|------|
| **市场概览** | 核心公司实时价格、90日涨跌幅走势、市值比较、产品分类 |
| **产业链全景** | 10 环节深度拆解（市场容量、供需缺口、市占率、PE比较、财务数据） |
| **产业情报** | 85+ 供应链关键指标、DeepSeek AI 分析、时间线、判断日志 |
| **TSM+EWY配置方案** | Gordon Growth DCF 估值 + 供需感知未来PE（v2） |
| **模拟组合** | 多组合管理、持仓跟踪（7段期间涨跌幅）、权重配置、PE/EPS基本面分析、AI调仓建议 |
| **关注组合** | 关注公司实时价格、PE_TTM、多期间收益、EPS增速及前瞻PE |
| **技术释义全景** | AI 七层架构（应用→大模型→框架→算力→存储→网络→制造）深度拆解 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 19 + Vite 8 + React Router 7 + Recharts 3 |
| 后端 | FastAPI + SQLAlchemy 2.0 + SQLite |
| 数据源 | 腾讯财经 API / yfinance / akshare / Naver API |
| AI | DeepSeek API（指标边际变化分析） |
| 采集器 | 14 行业数据源（NVIDIA IR、TSMC IR、TrendForce、WSTS/SIA 等） |

## 快速启动

```bash
# 后端
cd backend
pip install -r requirements.txt
python seed_data.py
uvicorn main:app --reload --port 8001

# 前端（新终端）
cd frontend
npm install
npm run dev
```

前端 `http://localhost:5173`，后端 `http://localhost:8001`，API 文档 `http://localhost:8001/docs`。

## 文档

详细文档请查看 [docs/](docs/index.md) 目录，基于 Diataxis 框架组织：

| 分类 | 内容 |
|------|------|
| [教程](docs/tutorial.md) | 从零启动并探索仪表盘 |
| [操作指南](docs/how-to/index.md) | 添加API端点、数据源、公司、估值场景 |
| [API 参考](docs/reference/api.md) | 30+ 端点详细说明 |
| [数据库参考](docs/reference/database.md) | 22+ 数据表结构 |
| [架构概览](docs/explanation/architecture.md) | 系统设计、数据流 |
| [估值方法论](docs/explanation/valuation.md) | Gordon Growth v1 + 供需感知 Future PE v2 |
| [数据源策略](docs/explanation/data-sources.md) | 5 数据源切换、14 采集器 |

## 项目结构

```
├── backend/
│   ├── main.py                 # FastAPI 应用（~30+ 端点）
│   ├── models.py               # SQLAlchemy 模型（22+ 表）
│   ├── schemas.py              # Pydantic 响应模型
│   ├── database.py             # SQLite 连接配置
│   ├── valuation.py            # Gordon Growth 估值引擎
│   ├── valuation_v2.py         # 供需感知未来PE估值引擎
│   ├── price_data.py           # 多源价格数据获取（腾讯/yfinance/akshare/Naver）
│   ├── ai_analysis.py          # DeepSeek AI 分析生成
│   ├── scheduler.py            # 定时采集调度
│   ├── seed_data.py            # 种子数据初始化
│   ├── startup_migration.py    # 启动迁移（新证券自动补入持久化DB）
│   ├── portfolio_tracking.py   # 组合跟踪（期间收益+PE/EPS计算）
│   ├── price_performance.py    # 相对收益表现计算
│   └── industry_collector/     # 14 行业数据采集器
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # 路由 & 导航（10+ 页面）
│   │   ├── api.js              # API 客户端（30+ 函数）
│   │   ├── pages/              # 页面组件
│   │   │   ├── Dashboard.jsx
│   │   │   ├── IndustryChain.jsx
│   │   │   ├── IndustryIntelligence.jsx
│   │   │   ├── PortfolioPage.jsx
│   │   │   ├── InvestmentPlan.jsx
│   │   │   ├── Companies.jsx
│   │   │   ├── TechGlossary.jsx
│   │   │   └── ...
│   │   └── components/         # PriceTicker, HotStocksPanel
│   └── vite.config.js          # Vite 配置（代理 /api → :8001）
└── docs/                       # 完整文档
```

## 数据源优先级

| 市场 | 优先 | 备选 |
|------|------|------|
| 美股 | 腾讯财经 API | yfinance |
| A 股 | akshare | yfinance |
| 港股 | akshare | yfinance |
| 韩国股 | Naver API | FinanceDataReader / yfinance |

## 估值模型

- **v1 Gordon Growth**: 两阶段 DCF，计算公允PE/市值/上涨空间和隐含增长率
- **v2 供需感知未来PE**: 产业链供需分数调整增长假设，输出低估/合理/高估信号

详见 [估值方法论](docs/explanation/valuation.md)。

## 前端页面

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 市场概览 | Dashboard 统计 + 价格走势 + 热点 |
| `/industry-chain` | 产业链全景 | 10 环节 + 公司详情 |
| `/industry-intelligence` | 产业情报 | 85+ 指标 + 时间线 |
| `/investment-plan` | TSM+EWY配置方案 | 估值模型 |
| `/portfolio` | 模拟组合 | 组合管理 |
| `/companies` | 公司列表 | 全部公司索引 |
| `/tech-glossary` | 技术释义全景 | AI 技术栈百科 |

## 笔记

- 服务器端口 8001（后端）、5173（前端）已在 `.gitignore` 和配置中引用
- 价格数据使用 SQLite 缓存层，API 不可用时自动回退缓存
- 韩国股票数据通过 Naver Mobile API 获取，韩元→美元汇率取 `₩1,300/$1`
- 部分 ticker（^SOX、000660.KS）在 yfinance 上有限流，腾讯 API 做首要替代
