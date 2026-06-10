import { useState, useEffect } from "react";
import { getTimeline, getJudgmentLogs, createJudgmentLog } from "../api";

const IMPACT_COLORS = { "重大": "badge-red", "中等": "badge-orange", "轻微": "badge-blue" };

function PriceReturnTable({ preReturns, postReturns }) {
  // Extract all tickers (excluding SOX which is the benchmark)
  const preTickers = preReturns ? Object.keys(preReturns).filter((t) => t !== "SOX") : [];
  const postTickers = postReturns ? Object.keys(postReturns).filter((t) => t !== "SOX") : [];
  const allTickers = [...new Set([...preTickers, ...postTickers])];

  if (allTickers.length === 0 && !(preReturns?.SOX || postReturns?.SOX)) return null;

  const fmt = (v) => {
    if (v == null) return "—";
    const sign = v > 0 ? "+" : "";
    return `${sign}${v.toFixed(1)}%`;
  };

  const color = (v) => {
    if (v == null) return "var(--text-secondary)";
    return v >= 0 ? "var(--success, #22c55e)" : "var(--error, #ef4444)";
  };

  return (
    <div style={{ marginTop: 10, fontSize: 12, overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 320 }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", padding: "4px 8px", borderBottom: "1px solid var(--border, #334155)", color: "var(--text-secondary, #94a3b8)", fontWeight: 500 }}>标的</th>
            <th style={{ textAlign: "right", padding: "4px 8px", borderBottom: "1px solid var(--border, #334155)", color: "var(--text-secondary, #94a3b8)", fontWeight: 500 }}>前10日</th>
            <th style={{ textAlign: "right", padding: "4px 8px", borderBottom: "1px solid var(--border, #334155)", color: "var(--text-secondary, #94a3b8)", fontWeight: 500 }}>后10日</th>
            <th style={{ textAlign: "right", padding: "4px 8px", borderBottom: "1px solid var(--border, #334155)", color: "var(--text-secondary, #94a3b8)", fontWeight: 500 }}>vs SOX</th>
          </tr>
        </thead>
        <tbody>
          {/* SOX benchmark row */}
          {(preReturns?.SOX || postReturns?.SOX) && (
            <tr>
              <td style={{ padding: "4px 8px", borderBottom: "1px solid var(--border, #334155)", fontWeight: 600 }}>SOX</td>
              <td style={{ padding: "4px 8px", borderBottom: "1px solid var(--border, #334155)", textAlign: "right", color: color(preReturns?.SOX?.abs) }}>
                {fmt(preReturns?.SOX?.abs)}
              </td>
              <td style={{ padding: "4px 8px", borderBottom: "1px solid var(--border, #334155)", textAlign: "right", color: color(postReturns?.SOX?.abs) }}>
                {fmt(postReturns?.SOX?.abs)}
              </td>
              <td style={{ padding: "4px 8px", borderBottom: "1px solid var(--border, #334155)", textAlign: "right", color: "var(--text-secondary, #94a3b8)" }}>基准</td>
            </tr>
          )}
          {allTickers.map((ticker) => {
            const pre = preReturns?.[ticker];
            const post = postReturns?.[ticker];
            return (
              <tr key={ticker}>
                <td style={{ padding: "4px 8px", borderBottom: "1px solid var(--border, #334155)", fontWeight: 600 }}>{ticker}</td>
                <td style={{ padding: "4px 8px", borderBottom: "1px solid var(--border, #334155)", textAlign: "right", color: color(pre?.abs) }}>
                  {fmt(pre?.abs)}
                </td>
                <td style={{ padding: "4px 8px", borderBottom: "1px solid var(--border, #334155)", textAlign: "right", color: color(post?.abs) }}>
                  {fmt(post?.abs)}
                </td>
                <td style={{ padding: "4px 8px", borderBottom: "1px solid var(--border, #334155)", textAlign: "right", color: color(pre?.rel) }}>
                  {pre?.rel != null ? fmt(pre.rel) : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function JudgmentTimelineCard({ event }) {
  const [expanded, setExpanded] = useState(false);
  const isJudgment = event.event_type === "judgment";

  const timeStr = event.event_time
    ? new Date(event.event_time).toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  return (
    <div
      className="card"
      style={{
        marginBottom: 12,
        borderLeft: isJudgment
          ? `4px solid ${
              event.impact_level === "重大"
                ? "var(--accent-red, #ef4444)"
                : event.impact_level === "中等"
                ? "var(--accent-orange, #f59e0b)"
                : "var(--accent-blue, #3b82f6)"
            }`
          : "4px solid var(--accent, #3b82f6)",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, color: "var(--text-secondary, #94a3b8)", fontWeight: 500 }}>
            {timeStr}
          </span>
          <span className={`badge ${isJudgment ? (IMPACT_COLORS[event.impact_level] || "badge-blue") : "badge-blue"}`}>
            {isJudgment ? event.impact_level || "判断" : "采集"}
          </span>
          {event.source_name && (
            <span style={{ fontSize: 10, color: "var(--text-secondary, #94a3b8)", padding: "1px 6px", background: "var(--card-bg-alt, #0f172a)", borderRadius: 4 }}>
              {event.source_name}
            </span>
          )}
        </div>
        {event.indicator_name_cn && (
          <span style={{ fontSize: 11, color: "var(--text-secondary, #94a3b8)" }}>
            {event.indicator_name_cn}
          </span>
        )}
      </div>

      {/* Title */}
      <h4 style={{ fontSize: 15, margin: 0, color: "var(--text, #f1f5f9)" }}>{event.title}</h4>

      {/* Description / value */}
      {event.description && (
        <p style={{ fontSize: 13, color: "var(--text-secondary, #94a3b8)", margin: "4px 0 6px" }}>{event.description}</p>
      )}
      {event.value_display && (
        <p style={{ fontSize: 14, fontWeight: 600, color: "var(--text, #f1f5f9)", margin: "4px 0 6px" }}>{event.value_display}</p>
      )}

      {/* Judgment-specific: expand to show before/after */}
      {isJudgment && (event.description || event.related_tickers) && (
        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            background: "none", border: "none", color: "var(--accent, #3b82f6)",
            cursor: "pointer", fontSize: 12, padding: 0, marginBottom: 4,
          }}
        >
          {expanded ? "收起详情 ▲" : "展开详情 ▼"}
        </button>
      )}

      {expanded && isJudgment && (
        <div style={{ marginBottom: 8 }}>
          {/* We don't have previous_view/new_view in the TimelineEvent, so we only show related info */}
          {event.related_tickers && (
            <div style={{ fontSize: 12, color: "var(--text-secondary, #94a3b8)", marginTop: 4 }}>
              <span>相关: {event.related_tickers}</span>
              {event.related_indicators && <span style={{ marginLeft: 12 }}>指标: {event.related_indicators}</span>}
            </div>
          )}
        </div>
      )}

      {/* Price performance table */}
      {(event.pre_event_returns || event.post_event_returns) && (
        <PriceReturnTable preReturns={event.pre_event_returns} postReturns={event.post_event_returns} />
      )}

      {/* Loading state for price data */}
      {event.related_tickers && !event.pre_event_returns && !event.post_event_returns && (
        <div style={{ fontSize: 11, color: "var(--text-secondary, #94a3b8)", marginTop: 6 }}>
          正在获取涨跌幅数据...
        </div>
      )}
    </div>
  );
}

function JudgmentLog() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    date: new Date().toISOString().slice(0, 10),
    title: "",
    description: "",
    previous_view: "",
    new_view: "",
    impact_level: "中等",
    related_companies: "",
    related_indicators: "",
    evidence: "",
    action_taken: "",
  });

  const fetchTimeline = () => {
    setLoading(true);
    const typeParam = filter === "all" ? null : filter;
    getJudgmentLogs().then((judgmentLogs) => {
      getTimeline(100, 0, typeParam)
        .then((tlEvents) => {
          // Merge: use timeline as primary source, but enrich with judgment log details
          setEvents(tlEvents || []);
        })
        .catch(() => setEvents([]))
        .finally(() => setLoading(false));
    });
  };

  useEffect(() => { fetchTimeline(); }, [filter]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    await createJudgmentLog(form);
    setShowForm(false);
    setForm({
      ...form,
      title: "", description: "", previous_view: "", new_view: "",
      evidence: "", action_taken: "",
    });
    fetchTimeline();
  };

  const filteredEvents = filter === "all"
    ? events
    : events.filter((e) => e.event_type === filter);

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "var(--text, #f1f5f9)" }}>
            时间线
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--text-secondary, #94a3b8)" }}>
            合并采集日志与判断日志 · 展示相关标的涨跌幅
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {/* Filter buttons */}
          <div style={{ display: "flex", borderRadius: 6, border: "1px solid var(--border, #334155)", overflow: "hidden" }}>
            {[
              { key: "all", label: "全部" },
              { key: "judgment", label: "判断" },
              { key: "collection", label: "采集" },
            ].map((f) => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                style={{
                  padding: "6px 14px",
                  border: "none",
                  background: filter === f.key ? "var(--accent, #3b82f6)" : "transparent",
                  color: filter === f.key ? "#fff" : "var(--text-secondary, #94a3b8)",
                  cursor: "pointer",
                  fontSize: 12,
                  fontWeight: filter === f.key ? 600 : 400,
                  transition: "all 0.15s",
                }}
              >
                {f.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => setShowForm(!showForm)}
            style={{
              padding: "6px 16px",
              borderRadius: 6,
              border: "1px solid var(--accent, #3b82f6)",
              background: showForm ? "var(--accent, #3b82f6)" : "transparent",
              color: "#fff",
              cursor: "pointer",
              fontSize: 13,
              whiteSpace: "nowrap",
            }}
          >
            {showForm ? "取消" : "+ 新增判断"}
          </button>
        </div>
      </div>

      {/* Add judgment form */}
      {showForm && (
        <form onSubmit={handleSubmit} className="card" style={{ marginBottom: 20 }}>
          <h3 style={{ marginBottom: 16 }}>新增判断变化</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>日期</label>
              <input type="date" value={form.date}
                onChange={(e) => setForm({ ...form, date: e.target.value })}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff" }} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>影响程度</label>
              <select value={form.impact_level}
                onChange={(e) => setForm({ ...form, impact_level: e.target.value })}
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
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff", minHeight: 60 }} />
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
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>相关公司（逗号分隔 ticker）</label>
              <input value={form.related_companies} onChange={(e) => setForm({ ...form, related_companies: e.target.value })}
                placeholder="例: NVDA,TSM,AMD"
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff" }} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>相关指标（逗号分隔）</label>
              <input value={form.related_indicators} onChange={(e) => setForm({ ...form, related_indicators: e.target.value })}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff" }} />
            </div>
            <div style={{ gridColumn: "1/-1" }}>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>证据/依据</label>
              <textarea value={form.evidence} onChange={(e) => setForm({ ...form, evidence: e.target.value })}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff", minHeight: 50 }} />
            </div>
            <div style={{ gridColumn: "1/-1" }}>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>采取行动</label>
              <input value={form.action_taken} onChange={(e) => setForm({ ...form, action_taken: e.target.value })}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff" }} />
            </div>
          </div>
          <button type="submit" style={{ marginTop: 16, padding: "10px 24px", background: "var(--accent-blue)", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer" }}>
            保存记录
          </button>
        </form>
      )}

      {/* Timeline entries */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 40, color: "var(--text-secondary)" }}>
          加载中...
        </div>
      ) : filteredEvents.length === 0 ? (
        <div style={{ textAlign: "center", padding: 40, color: "var(--text-secondary)" }}>
          {filter === "all"
            ? "暂无时间线事件。新增判断记录或等待数据采集后自动出现。"
            : filter === "judgment"
            ? "暂无判断日志"
            : "暂无采集日志"}
        </div>
      ) : (
        filteredEvents.map((event) => (
          <JudgmentTimelineCard key={event.id} event={event} />
        ))
      )}

      {/* Legend */}
      <div style={{
        marginTop: 20,
        padding: "8px 12px",
        fontSize: 11,
        color: "var(--text-secondary, #94a3b8)",
        borderTop: "1px solid var(--border, #334155)",
        display: "flex",
        gap: 16,
        flexWrap: "wrap",
      }}>
        <span>图例:</span>
        <span style={{ borderLeft: "4px solid var(--accent-red, #ef4444)", paddingLeft: 6 }}>判断·重大</span>
        <span style={{ borderLeft: "4px solid var(--accent-orange, #f59e0b)", paddingLeft: 6 }}>判断·中等</span>
        <span style={{ borderLeft: "4px solid var(--accent-blue, #3b82f6)", paddingLeft: 6 }}>判断·轻微 / 采集</span>
        <span>涨跌幅对标费城半导体指数(SOX)</span>
        <span>后10日数据在事件10天后自动更新</span>
      </div>
    </div>
  );
}

export default JudgmentLog;
