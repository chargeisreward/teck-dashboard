import { useState, useEffect } from "react";
import { getSequenceTimeline, getTimeline, getJudgmentLogs, createJudgmentLog } from "../api";

const IMPACT_COLORS = { "重大": "#ef4444", "中等": "#f59e0b", "轻微": "#3b82f6" };

function formatTime(isoStr) {
  if (!isoStr) return "";
  const d = new Date(isoStr);
  return d.toLocaleString("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

// ── 前值比较块 ──
function ComparisonBlock({ item }) {
  const currentVal = item.current_value;
  const unit = item.unit || "";

  return (
    <div style={{ marginTop: 8, display: "flex", gap: 12, flexWrap: "wrap" }}>
      {/* 当前值 */}
      <div style={{
        padding: "6px 10px", borderRadius: 6,
        background: "rgba(59,130,246,0.08)", borderLeft: "2px solid #3b82f6",
        minWidth: 100,
      }}>
        <div style={{ fontSize: 10, color: "var(--text-secondary)", marginBottom: 2 }}>当前值</div>
        <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text)" }}>
          {currentVal != null ? currentVal.toLocaleString() : "-"}
          {unit && <span style={{ fontSize: 10, fontWeight: 400, color: "var(--text-secondary)", marginLeft: 2 }}>{unit}</span>}
        </div>
        {item.change_pct != null && (
          <div style={{ fontSize: 11, color: item.change_pct >= 0 ? "var(--success, #22c55e)" : "var(--error, #ef4444)", fontWeight: 600 }}>
            {item.change_pct >= 0 ? "▲" : "▼"} {item.change_pct > 0 ? "+" : ""}{item.change_pct.toFixed(1)}%
          </div>
        )}
      </div>

      {/* 前值(单条) */}
      {item.previous_single && (
        <div style={{
          padding: "6px 10px", borderRadius: 6,
          background: "rgba(100,116,139,0.08)", borderLeft: "2px solid #64748b",
          minWidth: 100,
        }}>
          <div style={{ fontSize: 10, color: "var(--text-secondary)", marginBottom: 2 }}>前值 ({item.previous_single.date})</div>
          <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text)" }}>
            {item.previous_single.value != null ? item.previous_single.value.toLocaleString() : "-"}
            {unit && <span style={{ fontSize: 10, fontWeight: 400, color: "var(--text-secondary)", marginLeft: 2 }}>{unit}</span>}
          </div>
        </div>
      )}

      {/* 前值(多条) */}
      {item.previous_last && (
        <div style={{
          padding: "6px 10px", borderRadius: 6,
          background: "rgba(100,116,139,0.08)", borderLeft: "2px solid #64748b",
          minWidth: 100,
        }}>
          <div style={{ fontSize: 10, color: "var(--text-secondary)", marginBottom: 2 }}>前一条 ({item.previous_last.date})</div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
            {item.previous_last.value != null ? item.previous_last.value.toLocaleString() : "-"}
          </div>
        </div>
      )}
      {item.previous_max != null && (
        <div style={{ padding: "6px 10px", borderRadius: 6, background: "rgba(34,197,94,0.08)", borderLeft: "2px solid #22c55e", minWidth: 80 }}>
          <div style={{ fontSize: 10, color: "var(--text-secondary)", marginBottom: 2 }}>前值最高</div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#22c55e" }}>{item.previous_max.toLocaleString()}</div>
        </div>
      )}
      {item.previous_min != null && (
        <div style={{ padding: "6px 10px", borderRadius: 6, background: "rgba(239,68,68,0.08)", borderLeft: "2px solid #ef4444", minWidth: 80 }}>
          <div style={{ fontSize: 10, color: "var(--text-secondary)", marginBottom: 2 }}>前值最低</div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#ef4444" }}>{item.previous_min.toLocaleString()}</div>
        </div>
      )}

      {/* 边际变化 */}
      {item.marginal_change_pct != null && (
        <div style={{
          padding: "6px 10px", borderRadius: 6,
          background: item.marginal_change_pct >= 0 ? "rgba(34,197,94,0.06)" : "rgba(239,68,68,0.06)",
          borderLeft: `2px solid ${item.marginal_change_pct >= 0 ? "#22c55e" : "#ef4444"}`,
          minWidth: 80,
        }}>
          <div style={{ fontSize: 10, color: "var(--text-secondary)", marginBottom: 2 }}>边际变化</div>
          <div style={{
            fontSize: 13, fontWeight: 700,
            color: item.marginal_change_pct >= 0 ? "#22c55e" : "#ef4444",
          }}>
            {item.marginal_change_pct > 0 ? "+" : ""}{item.marginal_change_pct.toFixed(1)}%
          </div>
        </div>
      )}
    </div>
  );
}

// ── 序时卡片 ──
function SequenceCard({ item, index }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div style={{ display: "flex", gap: 12, position: "relative", paddingLeft: 30 }}>
      {/* 纵向时间轴 */}
      <div style={{
        position: "absolute", left: 0, top: 0, bottom: 0, width: 20,
        display: "flex", flexDirection: "column", alignItems: "center",
      }}>
        {/* 节点圆 */}
        <div style={{
          width: 12, height: 12, borderRadius: "50%",
          background: item.event_type === "judgment"
            ? (IMPACT_COLORS[item.impact_level] || "#3b82f6")
            : "#3b82f6",
          border: "2px solid var(--bg, #0f172a)",
          zIndex: 1, flexShrink: 0, marginTop: 14,
        }} />
        {/* 连接线 */}
        <div style={{ flex: 1, width: 2, background: "var(--border, #334155)", marginTop: 4 }} />
      </div>

      {/* 卡片内容 */}
      <div style={{
        flex: 1, marginBottom: 4, padding: "10px 14px",
        background: "var(--card-bg, #1e293b)",
        border: "1px solid var(--border, #334155)",
        borderRadius: 8,
        borderLeft: item.event_type === "judgment"
          ? `3px solid ${IMPACT_COLORS[item.impact_level] || "#3b82f6"}`
          : "3px solid #3b82f6",
      }}>
        {/* 头部 */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
            {formatTime(item.event_time)}
          </span>
          {item.event_type === "collection" && (
            <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 3, background: "#3b82f622", color: "#3b82f6", fontWeight: 600 }}>
              采集
            </span>
          )}
          {item.event_type === "judgment" && (
            <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 3, background: `${IMPACT_COLORS[item.impact_level] || "#3b82f6"}22`, color: IMPACT_COLORS[item.impact_level] || "#3b82f6", fontWeight: 600 }}>
              {item.impact_level || "判断"}
            </span>
          )}
          {item.source_name && (
            <span style={{ fontSize: 10, color: "var(--text-secondary)", padding: "1px 6px", background: "rgba(255,255,255,0.04)", borderRadius: 4 }}>
              {item.source_name}
            </span>
          )}
          <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--text-secondary)" }}>
            {item.indicator_name_cn || ""}
          </span>
        </div>

        {/* 标题 */}
        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text, #f1f5f9)" }}>
          {item.title}
        </div>

        {/* 原始显示值 */}
        {item.value_display && !item.current_value && (
          <div style={{ fontSize: 14, color: "var(--text)", marginTop: 2, fontWeight: 500 }}>
            {item.value_display}
          </div>
        )}

        {/* 比较值块 (采集事件) */}
        {(item.current_value != null || item.previous_single || item.previous_max != null) && (
          <ComparisonBlock item={item} />
        )}

        {/* 描述 */}
        {item.description && (
          <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 6 }}>{item.description}</div>
        )}

        {/* 影响分析 (DeepSeek) */}
        {(item.industry_impact || item.chain_impact || item.company_impact) && (
          <div style={{ marginTop: 8 }}>
            <button onClick={() => setExpanded(!expanded)}
              style={{ background: "none", border: "none", color: "var(--accent, #3b82f6)", cursor: "pointer", fontSize: 11, padding: 0 }}>
              {expanded ? "收起影响分析 ▲" : "展开影响分析 ▼"}
            </button>
            {expanded && (
              <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 6 }}>
                {item.industry_impact && (
                  <div style={{ fontSize: 12, padding: "6px 10px", background: "rgba(34,197,94,0.06)", borderRadius: 6, borderLeft: "2px solid #22c55e" }}>
                    <span style={{ fontWeight: 600, color: "#22c55e" }}>景气度: </span>{item.industry_impact}
                  </div>
                )}
                {item.chain_impact && (
                  <div style={{ fontSize: 12, padding: "6px 10px", background: "rgba(59,130,246,0.06)", borderRadius: 6, borderLeft: "2px solid #3b82f6" }}>
                    <span style={{ fontWeight: 600, color: "#3b82f6" }}>产业链: </span>{item.chain_impact}
                  </div>
                )}
                {item.company_impact && (
                  <div style={{ fontSize: 12, padding: "6px 10px", background: "rgba(245,158,11,0.06)", borderRadius: 6, borderLeft: "2px solid #f59e0b" }}>
                    <span style={{ fontWeight: 600, color: "#f59e0b" }}>公司: </span>{item.company_impact}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* 关联信息 */}
        {item.related_tickers && (
          <div style={{ fontSize: 10, color: "var(--text-secondary)", marginTop: 6, display: "flex", gap: 4, alignItems: "center" }}>
            <span>关联:</span>
            {item.related_tickers.split(",").map((t) => (
              <span key={t} style={{ padding: "1px 5px", background: "rgba(59,130,246,0.1)", borderRadius: 3 }}>{t.trim()}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Page (序时) ──
function SequenceTimeline() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("collection"); // "all" | "collection" | "judgment"

  const fetchData = () => {
    setLoading(true);
    getSequenceTimeline(100, 0)
      .then((data) => setEvents(data || []))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, []);

  const filtered = filter === "all"
    ? events
    : events.filter((e) => e.event_type === filter);

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "var(--text, #f1f5f9)" }}>
              产业情报 · 序时
            </h2>
            <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, background: "rgba(59,130,246,0.12)", color: "#3b82f6", fontWeight: 600 }}>
              纵向时间轴
            </span>
          </div>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--text-secondary, #94a3b8)" }}>
            比较值 · 当前值 · 影响解读
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {/* Filter */}
          <div style={{ display: "flex", borderRadius: 6, border: "1px solid var(--border, #334155)", overflow: "hidden" }}>
            {[
              { key: "collection", label: "采集" },
              { key: "judgment", label: "判断" },
              { key: "all", label: "全部" },
            ].map((f) => (
              <button key={f.key} onClick={() => setFilter(f.key)}
                style={{
                  padding: "6px 14px", border: "none",
                  background: filter === f.key ? "var(--accent, #3b82f6)" : "transparent",
                  color: filter === f.key ? "#fff" : "var(--text-secondary, #94a3b8)",
                  cursor: "pointer", fontSize: 12, fontWeight: filter === f.key ? 600 : 400,
                }}>
                {f.label}
              </button>
            ))}
          </div>
          <button onClick={fetchData} disabled={loading}
            style={{ padding: "6px 16px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--card-bg)", color: "var(--text)", fontSize: 13, cursor: loading ? "wait" : "pointer" }}>
            {loading ? "加载中..." : "刷新"}
          </button>
        </div>
      </div>

      {/* Timeline */}
      {loading && events.length === 0 ? (
        <div style={{ textAlign: "center", padding: 40, color: "var(--text-secondary)" }}>加载中...</div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: 40, color: "var(--text-secondary)" }}>
          {filter === "all" ? "暂无记录" : filter === "collection" ? "暂无采集记录" : "暂无判断记录"}
        </div>
      ) : (
        <div style={{ paddingTop: 8 }}>
          {filtered.map((item, i) => (
            <SequenceCard key={item.id || i} item={item} index={i} />
          ))}
        </div>
      )}

      {/* Legend */}
      <div style={{ marginTop: 20, padding: "8px 12px", fontSize: 11, color: "var(--text-secondary)", borderTop: "1px solid var(--border, #334155)", display: "flex", gap: 16, flexWrap: "wrap" }}>
        <span>图例:</span>
        <span style={{ color: "#3b82f6" }}>● 采集事件</span>
        <span style={{ color: "#ef4444" }}>● 判断·重大</span>
        <span style={{ color: "#f59e0b" }}>● 判断·中等</span>
        <span>前值最高/最低 = 历史统计</span>
        <span>影响分析由 DeepSeek AI 生成</span>
      </div>
    </div>
  );
}

export default SequenceTimeline;
