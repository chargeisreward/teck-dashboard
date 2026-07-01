import { useState, useEffect, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import {
  getIndustryIndicators, getIndustryDataSources, triggerIndustryCollect, getIndustryIndicator,
} from "../api";

import { Icon } from "../components/ui";

const CATEGORY_ORDER = [
  "raw_materials", "equipment", "eda", "chip_design", "foundry",
  "memory", "packaging", "distribution", "end_market", "gpu_cloud",
];

const CATEGORY_CN = {
  raw_materials: "原材料", equipment: "设备", eda: "EDA/设计工具",
  chip_design: "芯片设计", foundry: "晶圆制造", memory: "存储芯片",
  packaging: "先进封装/OSAT", distribution: "分销",
  end_market: "终端市场", gpu_cloud: "GPU云",
};

const CATEGORY_ICON_NAMES = {
  raw_materials: "rawMaterials",
  equipment: "equipment",
  eda: "eda",
  chip_design: "chipDesign",
  foundry: "foundry",
  memory: "memory",
  packaging: "packaging",
  distribution: "distribution",
  end_market: "endMarket",
  gpu_cloud: "gpuCloud",
};

function SourceStatusBadge({ source, lastUpdated, status }) {
  const statusColors = {
    ok: "var(--success, #22c55e)", stale: "var(--warning, #eab308)",
    outdated: "var(--error, #ef4444)", never: "var(--text-secondary, #888)",
  };
  return (
    <span title={`${source}: ${status === "ok" ? "今日更新" : status === "stale" ? "3日内" : status === "outdated" ? "超3日" : "从未采集"}`}
      style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12, padding: "2px 8px", borderRadius: 4, background: `${statusColors[status]}22`, color: statusColors[status] }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: statusColors[status], display: "inline-block" }} />
      {source}
    </span>
  );
}

function ChartPanel({ indicator }) {
  const [observations, setObservations] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!indicator) return;
    setLoading(true);
    getIndustryIndicator(indicator.id)
      .then((data) => {
        const sorted = (data.observations || []).sort((a, b) => new Date(a.date) - new Date(b.date));
        setObservations(sorted);
      })
      .finally(() => setLoading(false));
  }, [indicator?.id]);

  if (!observations.length) return <div style={{ padding: 20, textAlign: "center", color: "var(--text-secondary)" }}>{loading ? "加载中..." : "暂无历史数据"}</div>;

  return (
    <div style={{ width: "100%", height: 200, marginTop: 8 }}>
      <ResponsiveContainer>
        <LineChart data={observations.map((o) => ({ ...o, date: o.date.slice(0, 7) }))}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #334155)" />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--text-secondary, #94a3b8)" }} />
          <YAxis tick={{ fontSize: 11, fill: "var(--text-secondary, #94a3b8)" }} />
          <Tooltip contentStyle={{ background: "var(--card-bg, #1e293b)", border: "1px solid var(--border, #334155)", borderRadius: 4, fontSize: 12 }} />
          <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function IndicatorCard({ indicator, onExpand, isExpanded }) {
  const { name_cn, unit, latest_value, latest_date, change_pct, data_quality } = indicator;
  const hasData = latest_value != null;
  const isStale = indicator.last_updated && (Date.now() - new Date(indicator.last_updated).getTime()) > 7 * 86400000;

  return (
    <div onClick={() => hasData && onExpand?.(indicator)}
      style={{ background: "var(--card-bg, #1e293b)", border: "1px solid var(--border, #334155)", borderRadius: 8, padding: "12px 14px", cursor: hasData ? "pointer" : "default", opacity: hasData ? 1 : 0.5, minWidth: 160, flex: "1 1 180px" }}>
      <div style={{ fontSize: 11, color: "var(--text-secondary, #94a3b8)", marginBottom: 4 }}>
        {name_cn}
        {isStale && <span style={{ color: "var(--error, #ef4444)", marginLeft: 4 }}>(滞后)</span>}
      </div>
      {hasData ? (
        <>
          <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text, #f1f5f9)", lineHeight: 1.2 }}>
            {typeof latest_value === "number" ? latest_value.toLocaleString() : latest_value}
            {unit && <span style={{ fontSize: 11, fontWeight: 400, color: "var(--text-secondary, #94a3b8)", marginLeft: 4 }}>{unit}</span>}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4, fontSize: 12 }}>
            {change_pct != null && (
              <span style={{ color: change_pct >= 0 ? "var(--success, #22c55e)" : "var(--error, #ef4444)", fontWeight: 600 }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 2, color: change_pct >= 0 ? "var(--success)" : "var(--error)", fontWeight: 600 }}>
                <Icon name={change_pct >= 0 ? "up" : "down"} size={10} />
                {change_pct > 0 ? "+" : ""}{change_pct.toFixed(1)}%
              </span>
              </span>
            )}
            {latest_date && <span style={{ color: "var(--text-secondary, #94a3b8)", fontSize: 11 }}>{latest_date.slice(0, 7)}</span>}
            {data_quality === "estimated" && <span style={{ color: "var(--warning, #eab308)", fontSize: 10 }}>估算</span>}
          </div>
        </>
      ) : (
        <div style={{ fontSize: 14, color: "var(--text-secondary, #94a3b8)" }}>
          {indicator.description ? "暂无数据" : "待实现"}
        </div>
      )}
    </div>
  );
}

function SupplyChainSection({ category, indicators, expanded, onToggle, onExpandCard, expandedCard }) {
  const hasAny = indicators.length > 0;
  if (!hasAny) return null;

  const hasData = indicators.some((i) => i.latest_value != null);

  return (
    <div style={{ marginBottom: 16 }}>
      <div onClick={onToggle}
        style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", cursor: "pointer", borderRadius: "6px 6px 0 0", background: "var(--card-bg, #1e293b)", borderBottom: expanded ? "1px solid var(--border, #334155)" : "none", userSelect: "none" }}>
        <span style={{ fontSize: 16, display: "inline-flex", alignItems: "center" }}><Icon name={CATEGORY_ICON_NAMES[category]} size={18} /></span>
        <span style={{ fontWeight: 600, fontSize: 14, color: "var(--text, #f1f5f9)" }}>{CATEGORY_CN[category] || category}</span>
        <span style={{ fontSize: 11, color: "var(--text-secondary, #94a3b8)" }}>
          ({indicators.length}项{hasData ? `, ${indicators.filter(i => i.latest_value != null).length}项有数据` : ""})
        </span>
        <span style={{ marginLeft: "auto", color: "var(--text-secondary, #94a3b8)", fontSize: 12, display: "inline-flex", alignItems: "center", gap: 2 }}>
          {expanded ? "收起" : "展开"}
          <Icon name={expanded ? "collapse" : "expand"} size={12} />
        </span>
      </div>
      {expanded && (
        <div style={{ padding: 12, background: "var(--card-bg-alt, #0f172a)", border: "1px solid var(--border, #334155)", borderTop: "none", borderRadius: "0 0 8px 8px", display: "flex", flexWrap: "wrap", gap: 10 }}>
          {indicators.map((ind) => (
            <div key={ind.id} style={{ flex: "1 1 180px", minWidth: 160 }}>
              <IndicatorCard indicator={ind} onExpand={onExpandCard} isExpanded={expandedCard?.id === ind.id} />
              {expandedCard?.id === ind.id && <ChartPanel indicator={ind} />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function IndustryData() {
  const [indicators, setIndicators] = useState([]);
  const [dataSources, setDataSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [collecting, setCollecting] = useState(false);
  const [expandedSections, setExpandedSections] = useState(() =>
    CATEGORY_ORDER.reduce((a, c) => ({ ...a, [c]: true }), {})
  );
  const [expandedCard, setExpandedCard] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [inds, sources] = await Promise.all([
        getIndustryIndicators(),
        getIndustryDataSources(),
      ]);
      setIndicators(inds);
      setDataSources(sources);
    } catch (e) {
      console.error("Failed to fetch industry data:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleRefresh = async () => {
    setCollecting(true);
    try {
      await triggerIndustryCollect();
      await fetchData();
    } catch (e) {
      console.error("Collection failed:", e);
    } finally {
      setCollecting(false);
    }
  };

  const grouped = CATEGORY_ORDER
    .map((cat) => [cat, indicators.filter((i) => i.category === cat)])
    .filter(([_, list]) => list.length > 0);

  const latestUpdate = indicators
    .filter((i) => i.last_updated)
    .sort((a, b) => new Date(b.last_updated) - new Date(a.last_updated))[0]?.last_updated;

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "var(--text, #f1f5f9)" }}>
            数据浏览 · 产业
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--text-secondary, #94a3b8)" }}>
            {latestUpdate ? `最后更新: ${new Date(latestUpdate).toLocaleDateString("zh-CN")}` : "无数据"}
            {indicators.filter(i => i.latest_value != null).length > 0 &&
              ` · ${indicators.filter(i => i.latest_value != null).length}/${indicators.length}项有数据`}
          </p>
        </div>
        <button onClick={handleRefresh} disabled={collecting}
          style={{ padding: "6px 16px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--card-bg)", color: "var(--text)", fontSize: 13, cursor: collecting ? "wait" : "pointer", whiteSpace: "nowrap" }}>
          {collecting ? "采集中..." : "刷新全部"}
        </button>
      </div>

      {/* Data source status */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, padding: "8px 12px", marginBottom: 16, background: "var(--card-bg, #1e293b)", borderRadius: 8, border: "1px solid var(--border, #334155)" }}>
        <span style={{ fontSize: 12, color: "var(--text-secondary, #94a3b8)", marginRight: 4 }}>数据源:</span>
        {dataSources.map((ds) => (
          <SourceStatusBadge key={ds.source} source={ds.source} status={ds.status} lastUpdated={ds.last_updated} />
        ))}
        {dataSources.length === 0 && <span style={{ fontSize: 12, color: "var(--text-secondary, #94a3b8)" }}>暂无数据源信息</span>}
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 40, color: "var(--text-secondary)" }}>加载中...</div>
      ) : indicators.length === 0 ? (
        <div style={{ textAlign: "center", padding: 40, color: "var(--text-secondary)" }}>
          暂无产业数据。点击"刷新全部"开始采集，或等待数据源自动更新。
        </div>
      ) : (
        grouped.map(([cat, inds]) => (
          <SupplyChainSection key={cat} category={cat} indicators={inds}
            expanded={expandedSections[cat]}
            onToggle={() => setExpandedSections((prev) => ({ ...prev, [cat]: !prev[cat] }))}
            onExpandCard={(ind) => setExpandedCard(expandedCard?.id === ind.id ? null : ind)}
            expandedCard={expandedCard} />
        ))
      )}

      <div style={{ marginTop: 20, padding: "8px 12px", fontSize: 11, color: "var(--text-secondary)", borderTop: "1px solid var(--border, #334155)", display: "flex", gap: 16, flexWrap: "wrap" }}>
        <span>图例:</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <Icon name="up" size={10} /> 上升
          <Icon name="down" size={10} /> 下降
        </span>
        <span style={{ color: "var(--success, #22c55e)" }}>● 今日更新</span>
        <span style={{ color: "var(--warning, #eab308)" }}>● 3日内</span>
        <span style={{ color: "var(--error, #ef4444)" }}>● 超3日</span>
        <span>(滞后) = 超7日未更新</span>
        <span>每日6:00/18:00自动采集</span>
      </div>
    </div>
  );
}

export default IndustryData;
