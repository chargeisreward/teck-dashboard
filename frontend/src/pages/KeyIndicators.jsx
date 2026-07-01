import { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { getIndicators, getIndicatorCategories, getIndicatorObservations } from "../api";
import { Icon, Badge, EmptyState } from "../components/ui";

const CATEGORY_COLORS = {
  price_supply: "#3b82f6",
  industry: "#22c55e",
  lead_time: "#a855f7",
  financial: "#f97316",
  technology: "#06b6d4",
  sentiment: "#ec4899",
};

function KeyIndicators() {
  const [indicators, setIndicators] = useState([]);
  const [categories, setCategories] = useState([]);
  const [activeCategory, setActiveCategory] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [observations, setObservations] = useState([]);

  useEffect(() => {
    getIndicatorCategories().then(setCategories);
    getIndicators().then((inds) => {
      setIndicators(inds);
      if (inds.length > 0) setSelectedId(inds[0].id);
    });
  }, []);

  useEffect(() => {
    if (activeCategory) {
      getIndicators(activeCategory).then((inds) => {
        setIndicators(inds);
        if (inds.length > 0) setSelectedId(inds[0].id);
      });
    } else {
      getIndicators().then((inds) => {
        setIndicators(inds);
        if (inds.length > 0 && !inds.find((i) => i.id === selectedId)) {
          setSelectedId(inds[0].id);
        }
      });
    }
  }, [activeCategory]);

  useEffect(() => {
    if (selectedId) getIndicatorObservations(selectedId, 90).then(setObservations);
  }, [selectedId]);

  const selected = indicators.find((i) => i.id === selectedId);
  const chartData = [...observations]
    .sort((a, b) => new Date(a.date) - new Date(b.date))
    .map((o) => ({ date: o.date.slice(5), value: o.value }));

  const latestObs = observations.length > 0
    ? observations.reduce((a, b) => new Date(a.date) > new Date(b.date) ? a : b)
    : null;

  // 按分类分组显示
  const grouped = {};
  indicators.forEach((ind) => {
    if (!grouped[ind.category]) grouped[ind.category] = [];
    grouped[ind.category].push(ind);
  });

  // Data freshness calculation
  const freshnessLabel = (indicator) => {
    if (!indicator) return "";
    const freq = indicator.update_frequency;
    if (freq === "日度") return "每日更新";
    if (freq === "周度") return "每周更新";
    if (freq === "月度") return "每月更新";
    if (freq === "季度") return "每季更新";
    return freq;
  };

  return (
    <div>
      <div className="page-header">
        <h2>市场关键指标（24项）</h2>
        <p>可在互联网追踪访问的 AI 芯片产业链核心监测指标</p>
      </div>

      {/* 分类筛选 */}
      <div className="filter-bar">
        <button className={!activeCategory ? "active" : ""} onClick={() => setActiveCategory(null)}>全部 ({indicators.length})</button>
        {categories.map((cat) => (
          <button key={cat.category} className={activeCategory === cat.category ? "active" : ""}
            onClick={() => setActiveCategory(cat.category)}
            style={{ borderColor: activeCategory === cat.category ? "transparent" : CATEGORY_COLORS[cat.category] }}>
            {cat.name_cn} ({cat.count})
          </button>
        ))}
      </div>

      {/* 选中指标的详细图 */}
      {selected && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <h3 style={{ margin: 0 }}>{selected.name_cn || selected.name}</h3>
                <Badge variant={selected.is_automated ? "success" : "warning"}>
                  {selected.is_automated ? "可自动采集" : "需手动采集"}
                </Badge>
                <span style={{ fontSize: 12, color: "var(--text-secondary)", background: "rgba(255,255,255,0.05)", padding: "2px 8px", borderRadius: "var(--radius-sm)" }}>
                  {freshnessLabel(selected)}
                </span>
              </div>
              <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>{selected.description}</p>
            </div>
            {latestObs && (
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--accent)" }} className="font-numeric">
                  {latestObs.value} <span style={{ fontSize: 14, fontWeight: 400, color: "var(--text-secondary)" }}>{selected.unit}</span>
                </div>
                {latestObs.change_pct != null && (
                  <div style={{
                    fontSize: 13,
                    color: latestObs.change_pct > 0 ? "var(--success)" : "var(--error)",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 2,
                  }}>
                    <Icon name={latestObs.change_pct > 0 ? "up" : "down"} size={11} />
                    {latestObs.change_pct > 0 ? "+" : ""}{latestObs.change_pct}% 较前值
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 影响分析 */}
          {selected.impact_analysis && (
            <div style={{ padding: "10px 14px", background: "rgba(59,130,246,0.06)", borderRadius: 8, marginBottom: 12, fontSize: 13 }}>
              <span style={{ fontWeight: 600, color: "var(--accent-blue)" }}>影响分析: </span>
              {selected.impact_analysis}
            </div>
          )}

          {/* 数据来源 & 采集方法 */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12, fontSize: 13 }}>
            <div style={{ padding: "8px 12px", background: "rgba(255,255,255,0.03)", borderRadius: 6 }}>
              <span style={{ color: "var(--text-secondary)" }}>数据来源: </span>
              {selected.source_url ? (
                <a href={selected.source_url} target="_blank" rel="noopener noreferrer">
                  {selected.source} ↗
                </a>
              ) : (
                <span>{selected.source}</span>
              )}
            </div>
            <div style={{ padding: "8px 12px", background: "rgba(255,255,255,0.03)", borderRadius: 6 }}>
              <span style={{ color: "var(--text-secondary)" }}>采集频率: </span>
              {selected.update_frequency}
            </div>
          </div>

          {selected.collection_method && (
            <div className="timeline-impact-block warning">
              <span className="timeline-impact-label" style={{ color: "var(--warning)" }}>采集方法: </span>
              {selected.collection_method}
            </div>
          )}

          {/* 趋势图 */}
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} />
                <Tooltip
                  formatter={(val) => [`${val} ${selected.unit || ""}`]}
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                />
                <Line type="monotone" dataKey="value" stroke={CATEGORY_COLORS[selected.category] || "#3b82f6"} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState icon="sequence" title="暂无趋势数据" />
          )}
        </div>
      )}

      {/* 全部指标卡片网格 */}
      {categories.map((cat) => {
        const catIndicators = indicators.filter((i) => i.category === cat.category);
        if (catIndicators.length === 0) return null;
        return (
          <div key={cat.category} style={{ marginBottom: 24 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, color: CATEGORY_COLORS[cat.category] }}>
              {cat.name_cn} ({catIndicators.length})
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 12 }}>
              {catIndicators.map((ind) => {
                const isSelected = selectedId === ind.id;
                return (
                  <div key={ind.id}
                    className="card"
                    onClick={() => setSelectedId(ind.id)}
                    style={{
                      cursor: "pointer", padding: 14,
                      borderColor: isSelected ? CATEGORY_COLORS[ind.category] : undefined,
                      borderLeft: `3px solid ${isSelected ? CATEGORY_COLORS[ind.category] : "transparent"}`,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>{ind.name_cn || ind.name}</div>
                      <Badge variant={ind.is_automated ? "success" : "warning"}>
                        {ind.is_automated ? "自动" : "手动"}
                      </Badge>
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 8, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                      {ind.description}
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12 }}>
                      <span style={{ color: "var(--text-secondary)" }}>
                        {ind.source?.length > 25 ? ind.source.slice(0, 22) + "..." : ind.source}
                      </span>
                      <span style={{ color: "var(--text-secondary)" }}>
                        {ind.update_frequency}
                      </span>
                    </div>
                    {ind.source_url && (
                      <div style={{ marginTop: 6 }}>
                        <a href={ind.source_url} target="_blank" rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          style={{ fontSize: 11, color: "var(--accent)" }}>
                          数据源 ↗
                        </a>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default KeyIndicators;
