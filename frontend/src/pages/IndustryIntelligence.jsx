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

const TIER_CONFIG = {
  1: { label: "P0 核心", color: "#ef4444" },
  2: { label: "P1 重要", color: "#f59e0b" },
  3: { label: "P2 参考", color: "#64748b" },
};

// ── 边际变化配置 ──
const WINDOW_LABELS = {
  "30d": "30日变化",
  "90d": "90日变化",
  "last_change": "环比上期",
};

// ── Expanded Detail Panel ──
function ExpandedDetail({ indicator }) {
  const [observations, setObservations] = useState([]);
  const [loadingObs, setLoadingObs] = useState(false);

  useEffect(() => {
    if (!indicator) return;
    setLoadingObs(true);
    getIndustryIndicator(indicator.id)
      .then((data) => {
        const sorted = (data.observations || [])
          .sort((a, b) => new Date(a.date) - new Date(b.date));
        setObservations(sorted);
      })
      .finally(() => setLoadingObs(false));
  }, [indicator?.id]);

  return (
    <div style={{
      marginTop: 10, padding: "12px 14px",
      background: "rgba(59,130,246,0.04)",
      border: "1px solid rgba(59,130,246,0.15)",
      borderRadius: 8, width: "100%",
    }}>
      {/* 行业景气度 */}
      {indicator.industry_impact && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 4, fontWeight: 600 }}>📊 行业景气度</div>
          <div style={{
            fontSize: 12, color: "var(--text)", lineHeight: 1.5, padding: "6px 10px",
            background: "rgba(34,197,94,0.06)", borderRadius: 6, borderLeft: "2px solid #22c55e",
          }}>{indicator.industry_impact}</div>
        </div>
      )}

      {/* 产业链影响 */}
      {indicator.chain_impact && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 4, fontWeight: 600 }}>🔗 产业链影响</div>
          <div style={{
            fontSize: 12, color: "var(--text)", lineHeight: 1.5, padding: "6px 10px",
            background: "rgba(59,130,246,0.06)", borderRadius: 6, borderLeft: "2px solid #3b82f6",
          }}>{indicator.chain_impact}</div>
        </div>
      )}

      {/* 重点公司影响 */}
      {indicator.company_impact && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 4, fontWeight: 600 }}>🏢 重点公司</div>
          <div style={{
            fontSize: 12, color: "var(--text)", lineHeight: 1.5, padding: "6px 10px",
            background: "rgba(245,158,11,0.06)", borderRadius: 6, borderLeft: "2px solid #f59e0b",
          }}>{indicator.company_impact}</div>
        </div>
      )}

      {/* 历史曲线 */}
      <div style={{ marginTop: 8 }}>
        <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 6, fontWeight: 600 }}>📈 历史趋势</div>
        {loadingObs ? (
          <div style={{ fontSize: 11, color: "var(--text-secondary)", padding: 20, textAlign: "center" }}>加载中...</div>
        ) : observations.length > 1 ? (
          <div style={{ height: 160 }}>
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={observations}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #334155)" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--text-secondary)" }} tickFormatter={(v) => v.slice(0, 7)} />
                <YAxis tick={{ fontSize: 10, fill: "var(--text-secondary)" }} />
                <Tooltip contentStyle={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: 4, fontSize: 12 }} />
                <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot={{ r: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div style={{ fontSize: 11, color: "var(--text-secondary)", padding: 10, textAlign: "center" }}>暂无历史数据</div>
        )}
      </div>

      {/* 关联标的 */}
      {indicator.related_tickers && (
        <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 8 }}>
          <span>关联: </span>
          {indicator.related_tickers.split(",").map((t) => (
            <span key={t} style={{ padding: "1px 6px", background: "rgba(59,130,246,0.1)", borderRadius: 3, marginLeft: 4, fontSize: 10 }}>{t.trim()}</span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Indicator Card (截面卡片) ──
function IndicatorCard({ indicator, onToggleExpand, isExpanded }) {
  const hasData = indicator.latest_value != null;
  const change = indicator.change_pct;
  const marginalChange = indicator.marginal_change_pct;
  const windowLabel = WINDOW_LABELS[indicator.comparison_window] || "";
  const tierCfg = TIER_CONFIG[indicator.tier] || TIER_CONFIG[3];

  return (
    <div style={{
      background: "var(--card-bg, #1e293b)", border: isExpanded ? "1px solid #3b82f6" : "1px solid var(--border, #334155)",
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

      {hasData ? (
        <>
          {/* 当前值 */}
          <div style={{ fontSize: 18, fontWeight: 700, color: "var(--text, #f1f5f9)", lineHeight: 1.2 }}>
            {typeof indicator.latest_value === "number" ? indicator.latest_value.toLocaleString() : indicator.latest_value}
            {indicator.unit && <span style={{ fontSize: 11, fontWeight: 400, color: "var(--text-secondary)", marginLeft: 4 }}>{indicator.unit}</span>}
          </div>

          {/* 环比变化 */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2, fontSize: 12 }}>
            {change != null && (
              <span style={{ color: change >= 0 ? "var(--success, #22c55e)" : "var(--error, #ef4444)", fontWeight: 600 }}>
                {change >= 0 ? "▲" : "▼"} {change > 0 ? "+" : ""}{change.toFixed(1)}%
              </span>
            )}
            {indicator.latest_date && (
              <span style={{ color: "var(--text-secondary)", fontSize: 11 }}>{indicator.latest_date}</span>
            )}
          </div>

          {/* 边际变化 */}
          {marginalChange != null && (
            <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 1, fontSize: 11 }}>
              <span style={{
                color: marginalChange >= 0 ? "var(--success, #22c55e)" : "var(--error, #ef4444)",
                fontWeight: 500,
              }}>
                {marginalChange >= 0 ? "↑" : "↓"} {marginalChange > 0 ? "+" : ""}{marginalChange.toFixed(1)}%
              </span>
              {windowLabel && (
                <span style={{ color: "var(--text-secondary)", fontSize: 10 }}>{windowLabel}</span>
              )}
              {/* 景气度方向指示 */}
              <span style={{
                marginLeft: "auto", fontSize: 10, padding: "1px 6px", borderRadius: 3,
                background: marginalChange > 0 ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
                color: marginalChange > 0 ? "#22c55e" : "#ef4444",
                fontWeight: 600,
              }}>
                景气{marginalChange > 0 ? "↑" : "↓"}
              </span>
            </div>
          )}

          {/* AI分析 */}
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

          {/* 展开按钮 */}
          <button onClick={() => onToggleExpand?.(indicator)}
            style={{ background: "none", border: "none", color: "var(--accent, #3b82f6)", cursor: "pointer", fontSize: 11, padding: 0, marginTop: 6 }}>
            {isExpanded ? "收起分析 ▲" : "展开影响分析 ▼"}
          </button>

          {/* 展开的详细面板 */}
          {isExpanded && <ExpandedDetail indicator={indicator} />}
        </>
      ) : (
        <div style={{ fontSize: 13, color: "var(--text-secondary)", padding: "12px 0" }}>暂无数据</div>
      )}
    </div>
  );
}

// ── Supply Chain Section ──
function ChainSection({ category, indicators, expanded, onToggle, onExpandCard, expandedCard }) {
  const hasAny = indicators.length > 0;
  if (!hasAny) return null;

  // 计算该环节的整体景气方向
  const marginalChanges = indicators
    .map((i) => i.marginal_change_pct)
    .filter((v) => v != null);
  const avgMarginal = marginalChanges.length > 0
    ? marginalChanges.reduce((a, b) => a + b, 0) / marginalChanges.length
    : null;

  return (
    <div style={{ marginBottom: 14 }}>
      <div onClick={onToggle} style={{
        display: "flex", alignItems: "center", gap: 8, padding: "8px 12px",
        cursor: "pointer", borderRadius: "6px 6px 0 0",
        background: "var(--card-bg, #1e293b)",
        borderBottom: expanded ? "1px solid var(--border, #334155)" : "none",
        userSelect: "none",
      }}>
        <span style={{ fontSize: 14 }}>{CATEGORY_ICONS[category]}</span>
        <span style={{ fontWeight: 600, fontSize: 14, color: "var(--text, #f1f5f9)" }}>
          {CATEGORY_CN[category] || category}
        </span>
        {avgMarginal != null && (
          <span style={{
            fontSize: 11, padding: "1px 6px", borderRadius: 3,
            background: avgMarginal > 0 ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
            color: avgMarginal > 0 ? "#22c55e" : "#ef4444",
            fontWeight: 600,
          }}>
            景气{avgMarginal > 0 ? "↑" : "↓"} {avgMarginal > 0 ? "+" : ""}{avgMarginal.toFixed(1)}%
          </span>
        )}
        <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>({indicators.length}项)</span>
        <span style={{ marginLeft: "auto", color: "var(--text-secondary)", fontSize: 12 }}>
          {expanded ? "收起 ▲" : "展开 ▼"}
        </span>
      </div>
      {expanded && (
        <div style={{
          padding: 12, background: "var(--card-bg-alt, #0f172a)",
          border: "1px solid var(--border, #334155)", borderTop: "none",
          borderRadius: "0 0 8px 8px",
          display: "flex", flexWrap: "wrap", gap: 10,
        }}>
          {indicators.map((ind) => (
            <IndicatorCard key={ind.id} indicator={ind}
              onToggleExpand={onExpandCard}
              isExpanded={expandedCard?.id === ind.id} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Page (截面) ──
function IndustryIntelligence() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tierFilter, setTierFilter] = useState("all");
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

  const indicators = data?.indicators || [];
  const stats = data?.stats || {};

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

  if (loading && !data) {
    return (
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ textAlign: "center", padding: 60, color: "var(--text-secondary)" }}>
          <div style={{ fontSize: 14, marginBottom: 8 }}>加载中...</div>
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
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "var(--text, #f1f5f9)" }}>产业情报 · 截面</h2>
            <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, background: "rgba(59,130,246,0.12)", color: "#3b82f6", fontWeight: 600 }}>
              边际变化分析
            </span>
          </div>
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
              <textarea value={form.evidence} onChange={(e) => setForm({ ...form, evidence: e.target.value })}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff", minHeight: 50 }} />
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
          <ChainSection key={cat} category={cat} indicators={inds}
            expanded={expandedSections[cat]}
            onToggle={() => setExpandedSections((prev) => ({ ...prev, [cat]: !prev[cat] }))}
            onExpandCard={(ind) => setExpandedCard(expandedCard?.id === ind.id ? null : ind)}
            expandedCard={expandedCard} />
        ))
      )}

      {/* Legend */}
      <div style={{ marginTop: 20, padding: "8px 12px", fontSize: 11, color: "var(--text-secondary)", borderTop: "1px solid var(--border, #334155)", display: "flex", gap: 16, flexWrap: "wrap" }}>
        <span>图例:</span>
        <span style={{ color: TIER_CONFIG[1].color }}>■ P0 核心</span>
        <span style={{ color: TIER_CONFIG[2].color }}>■ P1 重要</span>
        <span style={{ color: TIER_CONFIG[3].color }}>■ P2 参考</span>
        <span>景气↑/↓ = 边际变化方向</span>
        <span>点击卡片展开 → 行业/产业链/公司影响分析</span>
        <span>分析由 DeepSeek AI 生成</span>
      </div>
    </div>
  );
}

export default IndustryIntelligence;
