import { useState, useEffect } from "react";
import { getSequenceTimeline, getTimeline, getJudgmentLogs, createJudgmentLog } from "../api";
import { Icon, Badge, EmptyState, ErrorState } from "../components/ui";

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
  const change = item.change_pct;
  const marginal = item.marginal_change_pct;

  return (
    <div className="comparison-block">
      {/* 当前值 */}
      <div className="comparison-item primary">
        <div className="comparison-item-label">当前值</div>
        <div className="comparison-item-value font-numeric">
          {currentVal != null ? currentVal.toLocaleString() : "-"}
          {unit && <span className="ii-indicator-card-unit">{unit}</span>}
        </div>
        {change != null && (
          <span className="comparison-item-change" style={{
            color: change >= 0 ? "var(--success)" : "var(--error)",
            display: "inline-flex", alignItems: "center", gap: 2,
          }}>
            <Icon name={change >= 0 ? "up" : "down"} size={10} />
            {change > 0 ? "+" : ""}{change.toFixed(1)}%
          </span>
        )}
      </div>

      {/* 前值(单条) */}
      {item.previous_single && (
        <div className="comparison-item">
          <div className="comparison-item-label">前值 ({item.previous_single.date})</div>
          <div className="comparison-item-value font-numeric">
            {item.previous_single.value != null ? item.previous_single.value.toLocaleString() : "-"}
            {unit && <span className="ii-indicator-card-unit">{unit}</span>}
          </div>
        </div>
      )}

      {/* 前值(多条) */}
      {item.previous_last && (
        <div className="comparison-item">
          <div className="comparison-item-label">前一条 ({item.previous_last.date})</div>
          <div className="comparison-item-value-sm font-numeric">
            {item.previous_last.value != null ? item.previous_last.value.toLocaleString() : "-"}
          </div>
        </div>
      )}
      {item.previous_max != null && (
        <div className="comparison-item success">
          <div className="comparison-item-label">前值最高</div>
          <div className="comparison-item-value-sm font-numeric" style={{ color: "var(--success)" }}>
            {item.previous_max.toLocaleString()}
          </div>
        </div>
      )}
      {item.previous_min != null && (
        <div className="comparison-item error">
          <div className="comparison-item-label">前值最低</div>
          <div className="comparison-item-value-sm font-numeric" style={{ color: "var(--error)" }}>
            {item.previous_min.toLocaleString()}
          </div>
        </div>
      )}

      {/* 边际变化 */}
      {marginal != null && (
        <div className={`comparison-item ${marginal >= 0 ? "success" : "error"}`}>
          <div className="comparison-item-label">边际变化</div>
          <div className="comparison-item-value-sm font-numeric" style={{
            color: marginal >= 0 ? "var(--success)" : "var(--error)",
          }}>
            {marginal > 0 ? "+" : ""}{marginal.toFixed(1)}%
          </div>
        </div>
      )}
    </div>
  );
}

// ── 序时卡片 ──
function SequenceCard({ item, index }) {
  const [expanded, setExpanded] = useState(false);

  const isJudgment = item.event_type === "judgment";
  const accentColor = isJudgment
    ? (IMPACT_COLORS[item.impact_level] || "var(--accent)")
    : "var(--accent)";

  return (
    <div className="timeline-card">
      {/* 纵向时间轴 */}
      <div className="timeline-axis">
        <div className="timeline-node" style={{ background: accentColor }} />
        <div className="timeline-line" />
      </div>

      {/* 卡片内容 */}
      <div className="timeline-card-content" style={{ borderLeftColor: accentColor }}>
        {/* 头部 */}
        <div className="timeline-card-header">
          <span className="timeline-card-time">{formatTime(item.event_time)}</span>
          {item.event_type === "collection" && (
            <Badge variant="accent">采集</Badge>
          )}
          {isJudgment && (
            <Badge
              variant={item.impact_level === "重大" ? "error" : item.impact_level === "中等" ? "warning" : "accent"}
              style={item.impact_level === "重大" ? { background: "rgba(239,68,68,0.15)", color: "#f87171" }
                : item.impact_level === "中等" ? { background: "rgba(245,158,11,0.15)", color: "#fbbf24" }
                : undefined}
            >
              {item.impact_level || "判断"}
            </Badge>
          )}
          {item.source_name && (
            <span className="comparison-item-label" style={{ padding: "1px 6px", background: "rgba(255,255,255,0.04)", borderRadius: "var(--radius-sm)" }}>
              {item.source_name}
            </span>
          )}
          <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--text-secondary)" }}>
            {item.indicator_name_cn || ""}
          </span>
        </div>

        {/* 标题 */}
        <div className="timeline-card-title">{item.title}</div>

        {/* 原始显示值 */}
        {item.value_display && !item.current_value && (
          <div className="timeline-card-value font-numeric">{item.value_display}</div>
        )}

        {/* 比较值块 (采集事件) */}
        {(item.current_value != null || item.previous_single || item.previous_max != null) && (
          <ComparisonBlock item={item} />
        )}

        {/* 描述 */}
        {item.description && (
          <div className="timeline-card-description">{item.description}</div>
        )}

        {/* 影响分析 (AI) */}
        {(item.industry_impact || item.chain_impact || item.company_impact) && (
          <div style={{ marginTop: 8 }}>
            <button onClick={() => setExpanded(!expanded)} className="timeline-card-toggle">
              {expanded ? "收起影响分析" : "展开影响分析"}
              <Icon name={expanded ? "collapse" : "expand"} size={10} />
            </button>
            {expanded && (
              <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 6 }}>
                {item.industry_impact && (
                  <div className="timeline-impact-block success">
                    <span className="timeline-impact-label" style={{ color: "var(--success)" }}>景气度: </span>{item.industry_impact}
                  </div>
                )}
                {item.chain_impact && (
                  <div className="timeline-impact-block accent">
                    <span className="timeline-impact-label" style={{ color: "var(--accent)" }}>产业链: </span>{item.chain_impact}
                  </div>
                )}
                {item.company_impact && (
                  <div className="timeline-impact-block warning">
                    <span className="timeline-impact-label" style={{ color: "var(--warning)" }}>公司: </span>{item.company_impact}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* 关联信息 */}
        {item.related_tickers && (
          <div className="timeline-related-tickers">
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
            <Badge variant="accent">纵向时间轴</Badge>
          </div>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--text-secondary, #94a3b8)" }}>
            比较值 · 当前值 · 影响解读
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {/* Filter */}
          <div style={{ display: "flex", borderRadius: "var(--radius-md)", border: "1px solid var(--border)", overflow: "hidden" }}>
            {[
              { key: "collection", label: "采集" },
              { key: "judgment", label: "判断" },
              { key: "all", label: "全部" },
            ].map((f) => (
              <button key={f.key} onClick={() => setFilter(f.key)}
                style={{
                  padding: "6px 14px", border: "none",
                  background: filter === f.key ? "var(--accent)" : "transparent",
                  color: filter === f.key ? "#fff" : "var(--text-secondary)",
                  cursor: "pointer", fontSize: 12, fontWeight: filter === f.key ? 600 : 400,
                }}>
                {f.label}
              </button>
            ))}
          </div>
          <button onClick={fetchData} disabled={loading}
            style={{ padding: "6px 16px", borderRadius: "var(--radius-md)", border: "1px solid var(--border)", background: "var(--bg-card)", color: "var(--text-primary)", fontSize: 13, cursor: loading ? "wait" : "pointer" }}>
            {loading ? "加载中..." : "刷新"}
          </button>
        </div>
      </div>

      {/* Timeline */}
      {loading && events.length === 0 ? (
        <div style={{ textAlign: "center", padding: 40, color: "var(--text-secondary)" }}>加载中...</div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon="sequence"
          title={filter === "all" ? "暂无记录" : filter === "collection" ? "暂无采集记录" : "暂无判断记录"}
          description="切换筛选器或刷新数据试试"
        />
      ) : (
        <div className="timeline-container">
          {filtered.map((item, i) => (
            <SequenceCard key={item.id || i} item={item} index={i} />
          ))}
        </div>
      )}

      {/* Legend */}
      <div style={{ marginTop: 20, padding: "8px 12px", fontSize: 11, color: "var(--text-secondary)", borderTop: "1px solid var(--border)", display: "flex", gap: 16, flexWrap: "wrap" }}>
        <span>图例:</span>
        <span style={{ color: "var(--accent)" }}>● 采集事件</span>
        <span style={{ color: "var(--error)" }}>● 判断·重大</span>
        <span style={{ color: "var(--warning)" }}>● 判断·中等</span>
        <span>前值最高/最低 = 历史统计</span>
        <span>影响分析由 MiniMax AI 生成</span>
      </div>
    </div>
  );
}

export default SequenceTimeline;
