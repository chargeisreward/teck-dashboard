import { useState } from "react";
import { LAYER_COLORS } from "../../data/techGlossaryData";

function StorageSubLayerCard({ layer, color }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className="sub-layer-card"
      style={{
        borderLeft: `4px solid ${color.border}`,
        background: color.bg,
      }}
    >
      <div className="sub-layer-header" onClick={() => setExpanded(!expanded)}>
        <div style={{ flex: 1 }}>
          <h4 style={{ color: color.text, marginBottom: 2 }}>{layer.name}</h4>
          <span style={{ color: "var(--text-secondary)", fontSize: 13 }}>
            {layer.nameEn} · {layer.map}
          </span>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontWeight: 700, fontSize: 18, color: "var(--text-primary)" }}>
            {layer.market}
          </div>
          <div style={{ color: "var(--text-secondary)", fontSize: 12 }}>全球市场规模</div>
        </div>
        <span
          className="expand-icon"
          style={{
            transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
            marginLeft: 12,
            fontSize: 20,
            color: "var(--text-secondary)",
          }}
        >
          ▼
        </span>
      </div>

      {expanded && (
        <div className="sub-layer-body" style={{ marginTop: 16 }}>
          <p style={{ color: "#cbd5e1", lineHeight: 1.7, marginBottom: 20, fontSize: 14 }}>
            {layer.desc}
          </p>

          <div className="detail-grid">
            {/* 市占率 */}
            <div className="detail-card">
              <h5>主要厂商 & 市占率</h5>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {layer.vendors.map((v, i) => (
                  <div key={i} className="vendor-row">
                    <span>{v.name}</span>
                    <div className="share-track">
                      <div
                        className="share-fill"
                        style={{
                          width: v.share,
                          background: [color.border, "#60a5fa", "#a78bfa"][i],
                        }}
                      />
                    </div>
                    <span className="share-value">{v.share}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 技术特性 */}
            <div className="detail-card">
              <h5>技术特性</h5>
              <p style={{ color: "#94a3b8", fontSize: 14, lineHeight: 1.7 }}>
                {layer.characteristics}
              </p>
            </div>

            {/* 技术壁垒 */}
            <div className="detail-card detail-card-full">
              <h5>核心技术壁垒</h5>
              <p style={{ color: "#f97316", fontSize: 14, fontWeight: 500, marginBottom: 8 }}>
                {layer.barrier}
              </p>
            </div>

            {/* 一句话难点 */}
            <div className="detail-card detail-card-full barrier-summary">
              <h5>一句话理解</h5>
              <p style={{ color: "#facc15", fontSize: 15, fontStyle: "italic", lineHeight: 1.6 }}>
                {layer.barrierShort}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── 标准层级组件 ────────────────────────────────────────────────────
function LayerCard({ layer, color, index }) {
  const [expanded, setExpanded] = useState(
    layer.id === "storage" || index === 0
  );

  return (
    <div
      id={`layer-${layer.id}`}
      className="layer-card"
      style={{ borderTop: `3px solid ${color.border}` }}
    >
      <div className="layer-header" onClick={() => setExpanded(!expanded)}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span
            className="layer-badge"
            style={{ background: color.bg, color: color.text, border: `1px solid ${color.border}` }}
          >
            L{index + 1}
          </span>
          <div>
            <h3 style={{ color: "var(--text-primary)", fontSize: 18 }}>
              {layer.title}{" "}
              <span style={{ fontWeight: 400, fontSize: 14, color: "var(--text-secondary)" }}>
                {layer.subtitle}
              </span>
            </h3>
          </div>
        </div>
        <div style={{ textAlign: "right", display: "flex", alignItems: "center", gap: 16 }}>
          <div>
            <span style={{ color: "var(--text-secondary)", fontSize: 12 }}>全球市场</span>
            <div style={{ fontWeight: 700, color: color.text }}>{layer.globalValue}</div>
          </div>
          <span
            className="expand-icon"
            style={{
              transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
              fontSize: 20,
              color: "var(--text-secondary)",
              transition: "transform 0.2s",
            }}
          >
            ▼
          </span>
        </div>
      </div>

      <p className="layer-desc">{layer.desc}</p>

      {expanded && (
        <div className="layer-body">
          {/* 如果是存储层且有子层级，显示子层级展开 */}
          {layer.subLayers ? (
            <div className="sub-layers-container">
              <div className="sub-layers-label" style={{ color: color.text }}>
                ═══ 存储五层深度拆解 ═══
              </div>
              {layer.subLayers.map((sl, i) => (
                <StorageSubLayerCard key={i} layer={sl} color={color} />
              ))}
            </div>
          ) : (
            /* 标准组件卡片 */
            <div className="components-grid">
              {layer.components.map((comp, i) => (
                <ComponentCard key={i} comp={comp} color={color} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── 组件详情卡片 ────────────────────────────────────────────────────
function ComponentCard({ comp, color }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className="comp-card"
      style={{
        border: `1px solid ${color.border}33`,
        background: `${color.bg}66`,
      }}
    >
      <div style={{ marginBottom: 12 }}>
        <h4 style={{ color: color.text, fontSize: 15, marginBottom: 2 }}>{comp.name}</h4>
        <p style={{ color: "#94a3b8", fontSize: 13 }}>{comp.desc}</p>
      </div>

      <div className="comp-stats">
        <div className="comp-stat">
          <span className="comp-stat-label">市场规模</span>
          <span className="comp-stat-value" style={{ color: color.text }}>
            {comp.market}
          </span>
        </div>
      </div>

      <div className="vendor-list">
        {comp.vendors.map((v, i) => (
          <div key={i} className="vendor-row">
            <span>{v.name}</span>
            <div className="share-track">
              <div
                className="share-fill"
                style={{
                  width: v.share,
                  background: [color.border, "#60a5fa", "#a78bfa"][i],
                }}
              />
            </div>
            <span className="share-value">{v.share}</span>
          </div>
        ))}
      </div>

      <button className="comp-detail-toggle" onClick={() => setExpanded(!expanded)}>
        {expanded ? "收起详情 ▲" : "展开技术详情 ▼"}
      </button>

      {expanded && (
        <div style={{ marginTop: 12, borderTop: `1px solid ${color.border}33`, paddingTop: 12 }}>
          <div className="comp-section">
            <span className="comp-section-label">技术特性</span>
            <p style={{ color: "#cbd5e1", fontSize: 13, lineHeight: 1.7 }}>{comp.characteristics}</p>
          </div>
          <div className="comp-section">
            <span className="comp-section-label" style={{ color: "#f97316" }}>技术壁垒</span>
            <p style={{ color: "#f97316", fontSize: 13, lineHeight: 1.5, opacity: 0.9 }}>
              {comp.barrier}
            </p>
          </div>
          <div className="comp-section barrier-box">
            <span className="comp-section-label" style={{ color: "#facc15" }}>一句话理解</span>
            <p style={{ color: "#facc15", fontSize: 14, fontStyle: "italic", lineHeight: 1.6 }}>
              {comp.barrierShort}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── 架构总览导航 ───────────────────────────────────────────────────
export { StorageSubLayerCard, LayerCard, ComponentCard };
