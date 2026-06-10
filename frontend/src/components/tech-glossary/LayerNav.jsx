import { LAYER_COLORS } from "../../data/techGlossaryData";

function LayerNav({ layers, activeLayer }) {
  return (
    <div className="layer-nav">
      {layers.map((layer, i) => (
        <a
          key={layer.id}
          href={`#layer-${layer.id}`}
          className={`layer-nav-item ${activeLayer === layer.id ? "active" : ""}`}
          style={{
            borderLeft: `3px solid ${LAYER_COLORS[i].border}`,
            "--hover-bg": LAYER_COLORS[i].bg,
          }}
        >
          <span
            className="nav-dot"
            style={{ background: LAYER_COLORS[i].border }}
          />
          <div>
            <div className="nav-label">{LAYER_COLORS[i].label}</div>
            <div className="nav-title">{layer.title}</div>
          </div>
        </a>
      ))}
    </div>
  );
}

// ─── 主页面 ─────────────────────────────────────────────────────────
export default LayerNav;
