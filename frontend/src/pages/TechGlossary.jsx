import { useState, useEffect, lazy, Suspense } from "react";
import { LAYERS, LAYER_COLORS } from "../data/techGlossaryData";

const LayerNav = lazy(() => import("../components/tech-glossary/LayerNav"));
const LayerCard = lazy(() => import("../components/tech-glossary/LayerCard").then((m) => ({ default: m.LayerCard })));

// ─── 主页面 ─────────────────────────────────────────────────────────
function TechGlossary() {
  const [activeLayer, setActiveLayer] = useState("application");

  // 监听滚动更新active layer
  useEffect(() => {
    const handleScroll = () => {
      const layerIds = LAYERS.map((l) => `layer-${l.id}`);
      for (let i = layerIds.length - 1; i >= 0; i--) {
        const el = document.getElementById(layerIds[i]);
        if (el && el.getBoundingClientRect().top <= window.innerHeight / 2) {
          setActiveLayer(LAYERS[i].id);
          break;
        }
      }
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className="tech-glossary">
      <div className="page-header">
        <h2>技术释义全景</h2>
        <p>从大模型到半导体制造 · AI 全栈技术架构深度拆解</p>
      </div>

      <div className="glossary-layout">
        {/* 侧边导航 */}
        <div className="glossary-sidebar">
          <div className="glossary-sidebar-inner">
            <h4 style={{ fontSize: 12, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 16 }}>
              AI 七层架构
            </h4>
            <Suspense fallback={<div style={{ padding: 12, fontSize: 12, color: "var(--text-secondary)" }}>加载导航...</div>}>
              <LayerNav layers={LAYERS} activeLayer={activeLayer} />
            </Suspense>
          </div>
        </div>

        {/* 主内容 */}
        <div className="glossary-content">
          {/* 概览图 */}
          <div className="overview-section">
            <h3>AI 全栈架构总览</h3>
            <p style={{ color: "#94a3b8", fontSize: 14, marginBottom: 20 }}>
              从大模型（软件）到芯片制造（硬件）的完整技术栈，每一层都是当前科技竞争的核心战场
            </p>
            <div className="overview-flow">
              {LAYERS.map((layer, i) => (
                <a
                  key={layer.id}
                  href={`#layer-${layer.id}`}
                  className="overview-node"
                  style={{
                    background: LAYER_COLORS[i].bg,
                    border: `1px solid ${LAYER_COLORS[i].border}44`,
                    color: LAYER_COLORS[i].text,
                  }}
                >
                  <span className="overview-arrow" style={{ color: LAYER_COLORS[i].border }}>
                    {i > 0 ? "↓" : ""}
                  </span>
                  <span className="overview-label">{LAYER_COLORS[i].label}</span>
                  <span className="overview-title">{layer.title}</span>
                  <span className="overview-value">{layer.globalValue}</span>
                </a>
              ))}
            </div>
          </div>

          {/* 各层详情 */}
          {LAYERS.map((layer, i) => (
            <Suspense key={layer.id} fallback={<div className="loading" style={{ padding: 20 }}>加载中...</div>}>
              <LayerCard layer={layer} color={LAYER_COLORS[i]} index={i} />
            </Suspense>
          ))}

          <div className="glossary-footer">
            <p>
              数据来源：Gartner、IDC、Yole、TrendForce、各公司财报、行业研报。
              市场数据为2025-2026年预测值，仅供参考。
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default TechGlossary;
