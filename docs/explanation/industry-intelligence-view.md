# 产业情报统一视图的设计

## 问题

项目中有多个页面/接口展示产业数据：

- `IndustryData.jsx`：按供应链位置展示指标卡片。
- `KeyIndicators.jsx`：旧版按主题分类的指标网格。
- `JudgmentLog.jsx`：时间线视图。

它们分别调用不同 API，数据口径不一致，用户需要在多个页面间切换才能看清“指标变化 → 影响分析 → 时间线 → 关联证券涨跌”的完整故事。

## 目标

用一个统一视图把以下信息串起来：

1. 指标按供应链环节分组，并分层 P0（核心）/ P1（重要）/ P2（参考）。
2. 每个指标显示最新值、上期值、环比变化、边际变化。
3. 关联证券 ±10 日涨跌幅（相对 SOX）。
4. 数据源头可追踪。
5. AI 生成的一句话分析逻辑。

## 关键概念

### 指标分层

`KeyIndicator.tier`：

- `1`：P0 核心指标（如 TSMC 月度营收、DRAM 合约价）。
- `2`：P1 重要指标。
- `3`：P2 参考指标（默认）。

前端 `IndustryIntelligence.jsx` 提供 P0/P1/P2/全部 筛选按钮。

### 边际变化

`IndicatorObservation.marginal_change_pct` 表示在频率感知窗口内的变化：

- 日/周频指标：与 30 天前比较。
- 月/季频指标：与 90 天前比较。
- 年频/不定期：与上一期观测值比较。

逻辑位于 `main.py` 的 `_compute_marginal_change` 与 `_determine_comparison_window`。

### 环比变化

`IndicatorObservation.change_pct` 是“最新值 vs 上一期观测值”的百分比，由采集器在写入时计算。

### TimelineEvent 事件总线

无论是人工判断还是自动采集，最终都写入 `TimelineEvent`：

- `event_type`：`judgment` 或 `collection`。
- `related_tickers`：关联证券。
- `pre_event_returns` / `post_event_returns`：±10 日绝对/相对收益 JSON。
- `indicator_observation_id`：关联到具体观测值。

统一视图的时间线部分直接读取这张表。

### 预/后事件收益

`price_performance.compute_relative_performance` 计算事件日前 10 个交易日与后 10 个交易日的收益，并以 SOX 为基准计算相对收益。

- 采集事件创建时立即计算 `pre_event_returns`。
- `post_event_returns` 在事件日后 10 个交易日才可用，由 `refresh_post_event_returns` 每 4 小时刷新。

### AI 分析

- `analysis`：一句话边际变化分析，由 `ai_analysis.generate_indicator_analysis` 生成。
- `industry_impact` / `chain_impact` / `company_impact`：三重影响分析，由 `ai_analysis.generate_industry_impact_analysis` 生成。

分析结果持久化到 `IndicatorObservation`，统一视图只读 DB，不实时调用 API。

## 数据流

```
┌──────────────────────────────────────────────────────────────┐
│  采集器 (industry_collector/sources/*.py)                     │
│  → BaseCollector._write_observation()                         │
│  → IndicatorObservation (value, change_pct, ...)              │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  调度器 (scheduler.py)                                        │
│  → collect_all() → TimelineEvent (pre_event_returns)          │
│  → batch_analyze_industry_impact() → AI 分析写入 observation  │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  GET /api/industry-intelligence                               │
│  → KeyIndicator + latest IndicatorObservation                 │
│  → pre/post returns from TimelineEvent                        │
│  → data source freshness + stats                              │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  IndustryIntelligence.jsx                                     │
│  → 按 category 分组 → TierFilter → IndicatorCard → TimelineFeed│
└──────────────────────────────────────────────────────────────┘
```

## 接口返回结构

见 [API 参考](../reference/api.md) 中的 `GET /api/industry-intelligence`。

## 设计取舍

| 权衡点 | 选择 | 代价 |
|---|---|---|
| 统一接口 vs 专用接口 | 保留旧接口并新增 `/api/industry-intelligence` | 旧接口仍需维护 |
| AI 实时生成 vs DB 缓存 | DB 缓存 | 新指标首次展示无分析，需等调度 |
| 收益实时计算 vs TimelineEvent 缓存 | TimelineEvent 缓存 | 需要额外调度刷新 post-event returns |
| P0/P1/P2 分层 | 数据库 tier 字段，默认 P2 | 需要人工维护 tier |

## 相关

- [AI 分析模块参考](../reference/ai-analysis.md)
- [数据源策略](data-sources.md)
- [API 参考](../reference/api.md)
- [如何记录判断变化](../how-to/index.md#如何记录一个判断变化)
