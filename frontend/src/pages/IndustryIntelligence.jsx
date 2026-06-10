import { useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { getIndustryIntelligence, getIndustryIndicator, createJudgmentLog } from "../api";

// ── Supply chain categories ──
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

const CATEGORY_ICONS = {
  raw_materials: "🧪", equipment: "🔧", eda: "💻",
  chip_design: "📐", foundry: "🏭", memory: "💾",
  packaging: "📦", distribution: "📡", end_market: "📊", gpu_cloud: "☁️",
};

const IMPACT_COLORS = { "重大": "#ef4444", "中等": "#f59e0b", "轻微": "#3b82f6" };

// ── Tier label config ──
const TIER_CONFIG = {
  1: { label: "P0 核心", color: "#ef4444" },
  2: { label: "P1 重要", color: "#f59e0b" },
  3: { label: "P2 参考", color: "#64748b" },
};

// ── Price Return Table Component (reused from JudgmentLog) ──
function PriceReturnTable({ preReturns, postReturns }) {
  const preTickers = preReturns ? Object.keys(preReturns).filter((t) => t !== "SOX") : [];
  const postTickers = postReturns ? Object.keys(postReturns).filter((t) => t !== "SOX") : [];
  const allTickers = [...new Set([...preTickers, ...postTickers])];

  if (allTickers.length === 0 && !(preReturns?.SOX || postReturns?.SOX)) return null;

  const fmt = (v) => v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
  const color = (v) => v == null ? "var(--text-secondary)" : v >= 0 ? "var(--success, #22c55e)" : "var(--error, #ef4444)";

  return (
    <div style={{ marginTop: 8, fontSize: 12, overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 280 }}>
        <thead>
          <tr>
            <th style={thStyle}>标的</th>
            <th style={{ ...thStyle, textAlign: "right" }}>前10日</th>
            <th style={{ ...thStyle, textAlign: "right" }}>后10日</th>
            <th style={{ ...thStyle, textAlign: "right" }}>vs SOX</th>
          </tr>
        </thead>
        <tbody>
          {(preReturns?.SOX || postReturns?.SOX) && (
            <tr>
              <td style={tdStyle}>SOX</td>
              <td style={{ ...tdStyle, textAlign: "right", color: color(preReturns?.SOX?.abs) }}>{fmt(preReturns?.SOX?.abs)}</td>
              <td style={{ ...tdStyle, textAlign: "right", color: color(postReturns?.SOX?.abs) }}>{fmt(postReturns?.SOX?.abs)}</td>
              <td style={{ ...tdStyle, textAlign: "right", color: "var(--text-secondary)" }}>基准</td>
            </tr>
          )}
          {allTickers.map((t) => {
            const pre = preReturns?.[t];
            const post = postReturns?.[t];
            return (
              <tr key={t}>
                <td style={tdStyle}>{t}</td>
                <td style={{ ...tdStyle, textAlign: "right", color: color(pre?.abs) }}>{fmt(pre?.abs)}</td>
                <td style={{ ...tdStyle, textAlign: "right", color: color(post?.abs) }}>{fmt(post?.abs)}</td>
                <td style={{ ...tdStyle, textAlign: "right", color: color(pre?.rel) }}>{pre?.rel != null ? fmt(pre.rel) : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const thStyle = { padding: "3px 8px", borderBottom: "1px solid var(--border, #334155)", color: "var(--text-secondary, #94a3b8)", fontWeight: 500, fontSize: 11 };
const tdStyle = { padding: "3px 8px", borderBottom: "1px solid var(--border, #334155)", fontWeight: 600, fontSize: 12 };

// ── Source Status Badge ──
function SourceBadge({ source, status }) {
  const colors = { ok: "#22c55e", stale: "#eab308", outdated: "#ef4444", never: "#64748b" };
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, padding: "2px 8px", borderRadius: 4, background: `${colors[status] || "#64748b"}22`, color: colors[status] || "#64748b" }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: colors[status] || "#64748b", display: "inline-block" }} />
      {source}
    </span>
  );
}

// ── Indicator Card ──
function IndicatorCard({ indicator, onToggleExpand, isExpanded }) {
  const hasData = indicator.latest_value != null;
  const change = indicator.change_pct;
  const tierCfg = TIER_CONFIG[indicator.tier] || TIER_CONFIG[3];

  return (
    <div style={{
      background: "var(--card-bg, #1e293b)", border: "1px solid var(--border, #334155)",
      borderRadius: 8, padding: "12px 14px", minWidth: 220, flex: "1 1 260px",
      transition: "border-color 0.2s",
    }}>
      {/* Header: name + tier badge */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text, #f1f5f9)" }}>
          {indicator.name_cn || indicator.name}
        </span>
        <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 3, background: `${tierCfg.color}22`, color: tierCfg.color, fontWeight: 600 }}>
          {tierCfg.label}
        </span>
      </div>

      {/* Value */}
      {hasData ? (
        <>
          <div style={{ fontSize: 18, fontWeight: 700, color: "var(--text, #f1f5f9)", lineHeight: 1.2 }}>
            {typeof indicator.latest_value === "number" ? indicator.latest_value.toLocaleString() : indicator.latest_value}
            {indicator.unit && <span style={{ fontSize: 11, fontWeight: 400, color: "var(--text-secondary)", marginLeft: 4 }}>{indicator.unit}</span>}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2, fontSize: 12 }}>
            {change != null && (
              <span style={{ color: change >= 0 ? "var(--success, #22c55e)" : "var(--error, #ef4444)", fontWeight: 600 }}>
                {change >= 0 ? "▲" : "▼"} {change > 0 ? "+" : ""}{change.toFixed(1)}%
              </span>
            )}
            {indicator.latest_date && (
              <span style={{ color: "var(--text-secondary)", fontSize: 11 }}>{indicator.latest_date}</span>
            )}
            <span style={{ fontSize: 10, color: "var(--text-secondary)", marginLeft: "auto" }}>
              {indicator.update_frequency || ""}
            </span>
          </div>

          {/* Analysis text */}
          {indicator.analysis && (
            <div style={{ marginTop: 6, fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5, padding: "6px 8px", background: "rgba(59,130,246,0.06)", borderRadius: 6, borderLeft: "2px solid #3b82f6" }}>
              {indicator.analysis}
            </div>
          )}

          {/* Source */}
          <div style={{ marginTop: 6, fontSize: 10, color: "var(--text-secondary)" }}>
            {indicator.source_url ? (
              <a href={indicator.source_url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--accent, #3b82f6)" }}>{indicator.source} ↗</a>
            ) : (
              <span>{indicator.source}</span>
            )}
          </div>
        </>
      ) : (
        <div style={{ fontSize: 13, color: "var(--text-secondary)", padding: "12px 0" }}>暂无数据</div>
      )}

      {/* Toggle price performance */}
      {indicator.related_tickers && (
        <button onClick={() => onToggleExpand?.(indicator)}
          style={{ background: "none", border: "none", color: "var(--accent, #3b82f6)", cursor: "pointer", fontSize: 11, padding: 0, marginTop: 6 }}>
          {isExpanded ? "收起涨跌幅 ▲" : "关联证券 ±10日 ▼"}
        </button>
      )}

      {isExpanded && hasData && (
        indicator.pre_event_returns || indicator.post_event_returns ? (
          <PriceReturnTable preReturns={indicator.pre_event_returns} postReturns={indicator.post_event_returns} />
        ) : (
          <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 6 }}>正在获取涨跌幅数据...</div>
        )
      )}
    </div>
  );
}

// ── Supply Chain Section ──
function ChainSection({ category, indicators, expanded, onToggle, onExpandCard, expandedCard }) {
  const hasAny = indicators.length > 0;
  if (!hasAny) return null;

  return (
    <div style={{ marginBottom: 14 }}>
      <div onClick={onToggle} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", cursor: "pointer", borderRadius: "6px 6px 0 0", background: "var(--card-bg, #1e293b)", borderBottom: expanded ? "1px solid var(--border, #334155)" : "none", userSelect: "none" }}>
        <span style={{ fontSize: 14 }}>{CATEGORY_ICONS[category]}</span>
        <span style={{ fontWeight: 600, fontSize: 14, color: "var(--text, #f1f5f9)" }}>{CATEGORY_CN[category] || category}</span>
        <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>({indicators.length}项)</span>
        <span style={{ marginLeft: "auto", color: "var(--text-secondary)", fontSize: 12 }}>{expanded ? "收起 ▲" : "展开 ▼"}</span>
      </div>
      {expanded && (
        <div style={{ padding: 12, background: "var(--card-bg-alt, #0f172a)", border: "1px solid var(--border, #334155)", borderTop: "none", borderRadius: "0 0 8px 8px", display: "flex", flexWrap: "wrap", gap: 10 }}>
          {indicators.map((ind) => (
            <IndicatorCard key={ind.id} indicator={ind} onToggleExpand={onExpandCard} isExpanded={expandedCard?.id === ind.id} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Timeline Feed (bottom section) ──
function TimelineFeed({ events, loading }) {
  const [filter, setFilter] = useState("all");

  const filtered = filter === "all" ? events : events.filter((e) => e.event_type === filter);

  if (loading) return <div style={{ textAlign: "center", padding: 20, color: "var(--text-secondary)" }}>加载中...</div>;

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "var(--text, #f1f5f9)" }}>时间线</h3>
        <div style={{ display: "flex", borderRadius: 6, border: "1px solid var(--border, #334155)", overflow: "hidden", marginLeft: 12 }}>
          {["all", "judgment", "collection"].map((f) => (
            <button key={f} onClick={() => setFilter(f)}
              style={{ padding: "4px 12px", border: "none", background: filter === f ? "var(--accent, #3b82f6)" : "transparent", color: filter === f ? "#fff" : "var(--text-secondary)", cursor: "pointer", fontSize: 12 }}>
              {f === "all" ? "全部" : f === "judgment" ? "判断" : "采集"}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: 20, color: "var(--text-secondary)" }}>暂无时间线事件</div>
      ) : (
        filtered.map((event) => (
          <div key={event.id} style={{
            marginBottom: 10, padding: "10px 14px",
            background: "var(--card-bg, #1e293b)",
            border: "1px solid var(--border, #334155)",
            borderRadius: 8,
            borderLeft: event.event_type === "judgment"
              ? `4px solid ${IMPACT_COLORS[event.impact_level] || "#3b82f6"}`
              : "4px solid #3b82f6",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4, flexWrap: "wrap" }}>
              <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
                {event.event_time ? new Date(event.event_time).toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : ""}
              </span>
              <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 3, fontWeight: 600, background: event.event_type === "judgment" ? `${IMPACT_COLORS[event.impact_level] || "#3b82f6"}22` : "#3b82f622", color: event.event_type === "judgment" ? (IMPACT_COLORS[event.impact_level] || "#3b82f6") : "#3b82f6" }}>
                {event.event_type === "judgment" ? (event.impact_level || "判断") : "采集"}
              </span>
              {event.source_name && <span style={{ fontSize: 10, color: "var(--text-secondary)", padding: "1px 6px", background: "var(--card-bg-alt, #0f172a)", borderRadius: 4 }}>{event.source_name}</span>}
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text, #f1f5f9)" }}>{event.title}</div>
            {event.value_display && <div style={{ fontSize: 14, color: "var(--text)", marginTop: 2 }}>{event.value_display}</div>}
            {event.description && <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2 }}>{event.description}</div>}

            {(event.pre_event_returns || event.post_event_returns) && (
              <PriceReturnTable preReturns={event.pre_event_returns} postReturns={event.post_event_returns} />
            )}
          </div>
        ))
      )}
    </div>
  );
}

// ── Main Page ──
function IndustryIntelligence() {
  const [searchParams] = useSearchParams();
  const timelineRef = useRef(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tierFilter, setTierFilter] = useState("all"); // "all" | 1 | 2 | 3
  const [expandedSections, setExpandedSections] = useState(() =>
    CATEGORY_ORDER.reduce((a, c) => ({ ...a, [c]: true }), {})
  );
  const [expandedCard, setExpandedCard] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    date: new Date().toISOString().slice(0, 10),
    title: "", description: "", previous_view: "", new_view: "",
    impact_level: "中等", related_companies: "", related_indicators: "",
    evidence: "", action_taken: "",
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getIndustryIntelligence();
      setData(result);
    } catch (e) {
      console.error("Failed to fetch industry intelligence:", e);
      setError("数据加载失败，请检查后端服务是否正常运行。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Scroll to timeline if ?tab=timeline
  useEffect(() => {
    if (data && searchParams.get("tab") === "timeline" && timelineRef.current) {
      setTimeout(() => timelineRef.current.scrollIntoView({ behavior: "smooth" }), 300);
    }
  }, [data, searchParams]);

  const indicators = data?.indicators || [];
  const timeline = data?.timeline || [];
  const stats = data?.stats || {};
  const dataSources = data?.data_sources || [];

  // Group by category
  const grouped = CATEGORY_ORDER
    .map((cat) => [cat, indicators.filter((i) => i.category === cat)])
    .filter(([_, list]) => list.length > 0);

  // Apply tier filter
  const filteredGrouped = tierFilter === "all"
    ? grouped
    : grouped.map(([cat, list]) => [cat, list.filter((i) => i.tier === tierFilter)])
        .filter(([_, list]) => list.length > 0);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await createJudgmentLog(form);
      setShowForm(false);
      setForm({ ...form, title: "", description: "", previous_view: "", new_view: "", evidence: "", action_taken: "" });
      fetchData();
    } catch (e) {
      console.error("Failed to create judgment:", e);
    }
  };

  const latestUpdate = indicators
    .filter((i) => i.last_updated)
    .sort((a, b) => new Date(b.last_updated) - new Date(a.last_updated))[0]?.last_updated;

  // ── Render ──
  if (loading && !data) {
    return (
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ textAlign: "center", padding: 60, color: "var(--text-secondary)" }}>
          <div style={{ fontSize: 14, marginBottom: 8 }}>加载中...</div>
          <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
            {[1, 2, 3].map((i) => (
              <div key={i} style={{ width: 240, height: 120, background: "var(--card-bg, #1e293b)", borderRadius: 8, animation: "pulse 1.5s infinite" }} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ textAlign: "center", padding: 60 }}>
          <div style={{ color: "var(--error, #ef4444)", fontSize: 16, marginBottom: 12 }}>{error}</div>
          <button onClick={fetchData} style={{ padding: "8px 20px", borderRadius: 6, border: "1px solid var(--border, #334155)", background: "var(--card-bg, #1e293b)", color: "var(--text)", cursor: "pointer" }}>
            重试
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "var(--text, #f1f5f9)" }}>产业情报</h2>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--text-secondary)" }}>
            {latestUpdate ? `最后更新: ${new Date(latestUpdate).toLocaleDateString("zh-CN")}` : ""}
            {stats.total_indicators > 0 && ` · ${stats.total_indicators}项指标 · ${stats.with_data}项有数据`}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={fetchData} disabled={loading}
            style={{ padding: "6px 16px", borderRadius: 6, border: "1px solid var(--border, #334155)", background: "var(--card-bg, #1e293b)", color: "var(--text, #f1f5f9)", fontSize: 13, cursor: loading ? "wait" : "pointer" }}>
            {loading ? "加载中..." : "刷新全部"}
          </button>
          <button onClick={() => setShowForm(!showForm)}
            style={{ padding: "6px 16px", borderRadius: 6, border: "1px solid var(--accent, #3b82f6)", background: showForm ? "var(--accent, #3b82f6)" : "transparent", color: "#fff", cursor: "pointer", fontSize: 13 }}>
            {showForm ? "取消" : "+ 新增判断"}
          </button>
        </div>
      </div>

      {/* Data source bar */}
      {dataSources.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, padding: "8px 12px", marginBottom: 12, background: "var(--card-bg, #1e293b)", borderRadius: 8, border: "1px solid var(--border, #334155)", alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "var(--text-secondary)", marginRight: 4 }}>数据源:</span>
          {dataSources.map((ds) => (
            <SourceBadge key={ds.source} source={ds.source} status={ds.status} />
          ))}
        </div>
      )}

      {/* Add judgment form */}
      {showForm && (
        <form onSubmit={handleSubmit} style={{ marginBottom: 16, padding: 16, background: "var(--card-bg, #1e293b)", border: "1px solid var(--border, #334155)", borderRadius: 8 }}>
          <h3 style={{ marginBottom: 12, fontSize: 15 }}>新增判断变化</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>日期</label>
              <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff" }} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>影响程度</label>
              <select value={form.impact_level} onChange={(e) => setForm({ ...form, impact_level: e.target.value })}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff" }}>
                <option>重大</option><option>中等</option><option>轻微</option>
              </select>
            </div>
            <div style={{ gridColumn: "1/-1" }}>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>标题</label>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff" }} />
            </div>
            <div style={{ gridColumn: "1/-1" }}>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>描述</label>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff", minHeight: 50 }} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>此前判断</label>
              <textarea value={form.previous_view} onChange={(e) => setForm({ ...form, previous_view: e.target.value })}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff", minHeight: 50 }} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>新判断</label>
              <textarea value={form.new_view} onChange={(e) => setForm({ ...form, new_view: e.target.value })}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff", minHeight: 50 }} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>相关公司 (ticker逗号分隔)</label>
              <input value={form.related_companies} onChange={(e) => setForm({ ...form, related_companies: e.target.value })} placeholder="NVDA,TSM,AMD"
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff" }} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>相关指标</label>
              <input value={form.related_indicators} onChange={(e) => setForm({ ...form, related_indicators: e.target.value })}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff" }} />
            </div>
            <div style={{ gridColumn: "1/-1" }}>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>证据/依据</label>
              <textarea value={form.evidence} onChange={(e) => setForm({ ...form, evidence: e.target.value })} style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff", minHeight: 50 }} />
            </div>
          </div>
          <button type="submit" style={{ marginTop: 12, padding: "8px 20px", background: "var(--accent-blue, #3b82f6)", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer" }}>保存记录</button>
        </form>
      )}

      {/* Tier filter */}
      <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
        <button onClick={() => { setTierFilter("all"); setExpandedCard(null); }}
          style={{ padding: "5px 14px", borderRadius: 6, border: "1px solid var(--border, #334155)", background: tierFilter === "all" ? "var(--accent, #3b82f6)" : "transparent", color: tierFilter === "all" ? "#fff" : "var(--text-secondary)", cursor: "pointer", fontSize: 12 }}>
          全部 ({stats.total_indicators || 0})
        </button>
        {[1, 2, 3].map((t) => {
          const cfg = TIER_CONFIG[t];
          const count = t === 1 ? stats.tier1_count : t === 2 ? stats.tier2_count : stats.tier3_count;
          return (
            <button key={t} onClick={() => { setTierFilter(t); setExpandedCard(null); }}
              style={{ padding: "5px 14px", borderRadius: 6, border: `1px solid ${cfg.color}`, background: tierFilter === t ? cfg.color : "transparent", color: tierFilter === t ? "#fff" : cfg.color, cursor: "pointer", fontSize: 12 }}>
              {cfg.label} ({count})
            </button>
          );
        })}
      </div>

      {/* Supply chain body */}
      {filteredGrouped.length === 0 ? (
        <div style={{ textAlign: "center", padding: 40, color: "var(--text-secondary)" }}>
          {tierFilter !== "all" ? "没有符合筛选条件的指标" : "暂无产业数据。点击「刷新全部」开始采集。"}
        </div>
      ) : (
        filteredGrouped.map(([cat, inds]) => (
          <ChainSection
            key={cat} category={cat} indicators={inds}
            expanded={expandedSections[cat]}
            onToggle={() => setExpandedSections((prev) => ({ ...prev, [cat]: !prev[cat] }))}
            onExpandCard={(ind) => setExpandedCard(expandedCard?.id === ind.id ? null : ind)}
            expandedCard={expandedCard}
          />
        ))
      )}

      {/* Timeline feed at bottom */}
      <div ref={timelineRef}>
        <TimelineFeed events={timeline} loading={loading && timeline.length === 0} />
      </div>

      {/* Legend */}
      <div style={{ marginTop: 20, padding: "8px 12px", fontSize: 11, color: "var(--text-secondary)", borderTop: "1px solid var(--border, #334155)", display: "flex", gap: 16, flexWrap: "wrap" }}>
        <span>图例:</span>
        <span style={{ color: TIER_CONFIG[1].color }}>■ P0 核心</span>
        <span style={{ color: TIER_CONFIG[2].color }}>■ P1 重要</span>
        <span style={{ color: TIER_CONFIG[3].color }}>■ P2 参考</span>
        <span>▲上涨 ▼下降</span>
        <span>涨跌幅对标费城半导体指数(SOX)</span>
        <span>分析由 DeepSeek AI 生成</span>
      </div>
    </div>
  );
}

export default IndustryIntelligence;
