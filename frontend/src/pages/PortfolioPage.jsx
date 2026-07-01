import { useState, useEffect, useCallback } from "react";
import {
  getFolioTracking, updateFolioWeight, getPriceHistory,
} from "../api";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { formatFinancial } from "../utils/formatNumber";
import { EmptyState } from "../components/ui";

const COLORS = ["#3b82f6", "#22c55e", "#a855f7", "#f97316", "#ef4444", "#06b6d4", "#f59e0b"];
const TICKER_COLORS = {
  NVDA: "#3b82f6", GOOGL: "#22c55e", TSM: "#a855f7", WDC: "#f97316", SNDK: "#06b6d4",
};

function fmt(val, decimals = 2) {
  return val != null && val !== undefined ? Number(val).toFixed(decimals) : "-";
}

function fmtPct(val) {
  if (val == null) return "-";
  const n = Number(val);
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}

function PriceCard({ ticker, name, price, changePct, peTtm }) {
  const color = changePct != null ? (changePct >= 0 ? "var(--accent-green)" : "var(--accent-red)") : "var(--text-secondary)";
  return (
    <div className="stat-card" style={{ minWidth: 160, flex: 1 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>{ticker}</span>
        <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>{name}</span>
      </div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>${fmt(price)}</div>
      <div style={{ fontSize: 13, color }}>
        {fmtPct(changePct)}
        {peTtm != null ? <span style={{ color: "var(--text-secondary)", marginLeft: 8 }}>PE: {formatFinancial(peTtm, 1)}x</span> : null}
      </div>
    </div>
  );
}

function Skeleton({ height = 120 }) {
  return (
    <div style={{
      height, borderRadius: 8, background: "var(--bg-secondary)",
      animation: "pulse 1.5s ease-in-out infinite",
      display: "flex", alignItems: "center", justifyContent: "center",
      color: "var(--text-secondary)", fontSize: 13,
    }}>
      加载中...
    </div>
  );
}

function PortfolioPage() {
  const [tracking, setTracking] = useState(null);
  const [priceHistory, setPriceHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [updatingWeight, setUpdatingWeight] = useState(null);
  const [activeSection, setActiveSection] = useState("returns");

  const loadTracking = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const track = await getFolioTracking();
      setTracking(track);

      // Load 90-day price history for chart
      const tickers = track.holdings?.map((h) => h.ticker) || [];
      const historyPromises = tickers.map((t) =>
        getPriceHistory(t, 90).then((resp) => ({ ticker: t, data: resp.data || [] })).catch(() => ({ ticker: t, data: [] }))
      );
      const histories = await Promise.all(historyPromises);
      setPriceHistory(histories);
    } catch (err) {
      setError(err.message || "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTracking();
  }, [loadTracking]);

  // ── 90日归一化图表数据处理 ──
  const chartData = (() => {
    if (priceHistory.length === 0) return [];
    const dateMap = {};
    priceHistory.forEach(({ ticker, data }) => {
      if (!data || data.length === 0) return;
      const base = data[0]?.price || 1;
      data.forEach((d) => {
        const key = d.date?.slice(5) || "";
        if (!dateMap[key]) dateMap[key] = { date: key };
        dateMap[key][ticker] = base > 0 ? ((d.price / base - 1) * 100) : 0;
      });
    });
    return Object.values(dateMap).sort((a, b) => a.date.localeCompare(b.date));
  })();

  const holdings = tracking?.holdings || [];
  const chartWithPortfolio = chartData.map((point) => {
    let weightedSum = 0;
    let weightTotal = 0;
    holdings.forEach((h) => {
      if (point[h.ticker] != null && h.weight > 0) {
        weightedSum += point[h.ticker] * h.weight;
        weightTotal += h.weight;
      }
    });
    return {
      ...point,
      portfolio: weightTotal > 0 ? weightedSum / weightTotal : null,
    };
  });

  // ── 权重调整 ──
  const handleWeightChange = async (followId, newWeight) => {
    newWeight = Math.max(0, Math.min(100, Math.round(newWeight * 10) / 10));
    setUpdatingWeight(followId);
    try {
      await updateFolioWeight(followId, newWeight);
      await loadTracking();
    } catch (e) {
      console.error("权重更新失败", e);
    } finally {
      setUpdatingWeight(null);
    }
  };

  // ── 刷新 ──
  const handleRefresh = () => {
    loadTracking();
  };

  const tickersInChart = [...new Set(priceHistory.map((h) => h.ticker))];

  // ── Empty state ──
  if (!loading && (!tracking || holdings.length === 0)) {
    return (
      <div>
        <div className="page-header">
          <div>
            <h2>跟踪组合</h2>
            <p>暂无关注公司，请在市场概览页面添加关注</p>
          </div>
        </div>
        <div className="card" style={{ textAlign: "center", padding: 60 }}>
          <EmptyState
            icon="portfolio"
            title="暂无关注公司"
            description="前往市场概览页面，点击公司卡片上的关注按钮添加关注"
          />
        </div>
      </div>
    );
  }

  // ── Error state ──
  if (error && !tracking) {
    return (
      <div>
        <div className="page-header"><h2>跟踪组合</h2></div>
        <div className="card" style={{ textAlign: "center", padding: 40, borderLeft: "4px solid var(--accent-red)" }}>
          <p style={{ color: "var(--accent-red)", marginBottom: 16 }}>加载失败: {error}</p>
          <button
            onClick={handleRefresh}
            style={{
              padding: "8px 24px", borderRadius: 6, border: "none",
              background: "var(--accent-blue)", color: "#fff", cursor: "pointer",
            }}
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* ── Header ── */}
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h2>跟踪组合</h2>
          <p>核心公司实时跟踪与权重配置</p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {tracking?.last_updated && (
            <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
              最后更新: {tracking.last_updated}
            </span>
          )}
          <button
            onClick={handleRefresh}
            disabled={loading}
            style={{
              padding: "8px 16px", borderRadius: 6, border: "1px solid var(--border)",
              background: "var(--bg-secondary)", color: "#fff", cursor: "pointer", fontSize: 13,
            }}
          >
            {loading ? "加载中..." : "刷新"}
          </button>
        </div>
      </div>

      {loading && !tracking ? (
        <>
          <Skeleton height={100} />
          <div style={{ marginTop: 16 }}><Skeleton height={200} /></div>
        </>
      ) : tracking ? (
        <>
          {/* ── 核心公司实时价格 ── */}
          <div className="stats-grid" style={{ gridTemplateColumns: `repeat(${Math.min(holdings.length, 5)}, 1fr)` }}>
            {holdings.map((h) => (
              <PriceCard
                key={h.holding_id}
                ticker={h.ticker}
                name={h.name_cn || h.company_name}
                price={h.current_price}
                changePct={h.change_pct}
                peTtm={h.pe_ttm}
              />
            ))}
          </div>

          {/* ── 组合统计卡片 ── */}
          <div className="stats-grid" style={{ marginTop: 16 }}>
            <div className="stat-card">
              <div className="label">持仓权重</div>
              <div className="value blue" style={{ fontSize: 22 }}>{fmt(tracking.total_weight, 1)}%</div>
            </div>
            <div className="stat-card">
              <div className="label">{tracking.cash_weight >= 0 ? "现金" : "负现金"}</div>
              <div className="value" style={{ fontSize: 22, color: tracking.cash_weight >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>
                {fmt(tracking.cash_weight, 1)}%
              </div>
            </div>
            <div className="stat-card">
              <div className="label">组合 PE (加权)</div>
              <div className="value purple" style={{ fontSize: 22 }}>{fmt(tracking.weighted_pe, 1)}</div>
            </div>
            <div className="stat-card">
              <div className="label">过去90天组合涨跌</div>
              <div className="value" style={{ fontSize: 22, color: (tracking.weighted_return_3m || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>
                {fmtPct(tracking.weighted_return_3m)}
              </div>
            </div>
          </div>

          {/* ── 权重配置面板 ── */}
          <div className="card" style={{ marginTop: 16 }}>
            <h3>权重配置</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {holdings.map((h, i) => (
                <div key={h.holding_id} style={{
                  display: "flex", alignItems: "center", gap: 12,
                  padding: "10px 12px", borderRadius: 6,
                  background: "var(--bg-secondary)",
                }}>
                  <div style={{
                    width: 4, height: 32, borderRadius: 2,
                    background: TICKER_COLORS[h.ticker] || COLORS[i % COLORS.length],
                  }} />
                  <div style={{ minWidth: 90 }}>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{h.ticker}</div>
                    <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>{h.name_cn || h.company_name}</div>
                  </div>
                  <div style={{ fontSize: 13, color: "var(--text-secondary)", minWidth: 70 }}>
                    ${fmt(h.current_price)}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 4, marginLeft: "auto" }}>
                    <button
                      onClick={() => handleWeightChange(h.holding_id, (h.weight || 0) - 5)}
                      disabled={updatingWeight === h.holding_id || (h.weight || 0) <= 0}
                      style={{
                        width: 32, height: 32, borderRadius: 6, border: "1px solid var(--border)",
                        background: "transparent", color: "#fff", cursor: "pointer",
                        fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center",
                        opacity: (h.weight || 0) <= 0 ? 0.4 : 1,
                      }}
                    >−</button>
                    <input
                      type="number"
                      value={h.weight}
                      min={0}
                      max={100}
                      step={1}
                      onChange={(e) => {
                        const v = parseFloat(e.target.value);
                        if (!isNaN(v)) handleWeightChange(h.holding_id, v);
                      }}
                      style={{
                        width: 56, padding: "6px 8px", borderRadius: 6, border: "1px solid var(--border)",
                        background: "var(--bg)", color: "#fff", textAlign: "center", fontSize: 14, fontWeight: 600,
                      }}
                    />
                    <button
                      onClick={() => handleWeightChange(h.holding_id, (h.weight || 0) + 5)}
                      disabled={updatingWeight === h.holding_id || (h.weight || 0) >= 100}
                      style={{
                        width: 32, height: 32, borderRadius: 6, border: "1px solid var(--border)",
                        background: "transparent", color: "#fff", cursor: "pointer",
                        fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center",
                        opacity: (h.weight || 0) >= 100 ? 0.4 : 1,
                      }}
                    >+</button>
                    <span style={{ fontSize: 13, color: "var(--text-secondary)", minWidth: 50, textAlign: "right" }}>
                      {updatingWeight === h.holding_id ? "..." : `${fmt(h.weight, 1)}%`}
                    </span>
                  </div>
                </div>
              ))}
              {/* 现金行 */}
              <div style={{
                display: "flex", alignItems: "center", gap: 12,
                padding: "10px 12px", borderRadius: 6,
                background: "var(--bg-secondary)", opacity: 0.8,
              }}>
                <div style={{ width: 4, height: 32, borderRadius: 2, background: "var(--text-secondary)" }} />
                <div style={{ minWidth: 90 }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>现金</div>
                </div>
                <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>—</div>
                <div style={{ marginLeft: "auto" }}>
                  <span style={{
                    fontSize: 16, fontWeight: 700,
                    color: tracking.cash_weight >= 0 ? "var(--accent-green)" : "var(--accent-red)",
                  }}>
                    {fmt(tracking.cash_weight, 1)}%
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* ── 90日涨跌幅图表 ── */}
          <div className="card chart-full" style={{ marginTop: 16 }}>
            <h3>90日涨跌幅走势（归一化）</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartWithPortfolio}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} tickFormatter={(v) => `${v.toFixed(1)}%`} />
                <Tooltip
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
                  formatter={(v, name) => [`${Number(v).toFixed(2)}%`, name]}
                />
                {tickersInChart.map((t, i) => (
                  <Line
                    key={t}
                    type="monotone"
                    dataKey={t}
                    stroke={TICKER_COLORS[t] || COLORS[i % COLORS.length]}
                    strokeWidth={1.5}
                    dot={false}
                    name={t}
                  />
                ))}
                <Line
                  type="monotone"
                  dataKey="portfolio"
                  stroke="#fff"
                  strokeWidth={2.5}
                  dot={false}
                  name="组合加权"
                  strokeDasharray="4 2"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* ── 期间收益 / EPS 表格切换 ── */}
          <div className="filter-bar" style={{ marginTop: 16 }}>
            <button
              className={activeSection === "returns" ? "active" : ""}
              onClick={() => setActiveSection("returns")}
            >
              期间收益
            </button>
            <button
              className={activeSection === "eps" ? "active" : ""}
              onClick={() => setActiveSection("eps")}
            >
              EPS & 前瞻 PE
            </button>
          </div>

          {/* ── 期间收益表格 ── */}
          {activeSection === "returns" && (
            <div className="card" style={{ marginTop: 8 }}>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>公司</th>
                      <th>PE_TTM</th>
                      <th>当天</th>
                      <th>1周</th>
                      <th>1月</th>
                      <th>3月</th>
                      <th>6月</th>
                      <th>1年</th>
                      <th>3年</th>
                    </tr>
                  </thead>
                  <tbody>
                    {holdings.map((h, i) => (
                      <tr key={h.holding_id}>
                        <td>
                          <span style={{
                            display: "inline-block", width: 8, height: 8, borderRadius: "50%",
                            background: TICKER_COLORS[h.ticker] || COLORS[i % COLORS.length],
                            marginRight: 6,
                          }} />
                          <strong>{h.ticker}</strong>
                          <span style={{ color: "var(--text-secondary)", fontSize: 11, marginLeft: 4 }}>
                            {h.name_cn || h.company_name}
                          </span>
                        </td>
                        <td>{h.pe_ttm != null ? `${formatFinancial(h.pe_ttm, 1)}x` : "-"}</td>
                        <td style={{ color: (h.return_1d || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>{fmtPct(h.return_1d)}</td>
                        <td style={{ color: (h.return_1w || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>{fmtPct(h.return_1w)}</td>
                        <td style={{ color: (h.return_1m || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>{fmtPct(h.return_1m)}</td>
                        <td style={{ color: (h.return_3m || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>{fmtPct(h.return_3m)}</td>
                        <td style={{ color: (h.return_6m || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>{fmtPct(h.return_6m)}</td>
                        <td style={{ color: (h.return_1y || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>{fmtPct(h.return_1y)}</td>
                        <td style={{ color: (h.return_3y || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>{fmtPct(h.return_3y)}</td>
                      </tr>
                    ))}
                    {/* 组合加权行 */}
                    <tr style={{ fontWeight: 700, background: "rgba(255,255,255,0.04)", borderTop: "2px solid var(--accent-blue)" }}>
                      <td><span style={{ color: "var(--accent-blue)" }}>组合加权</span></td>
                      <td style={{ color: "var(--accent-blue)" }}>{tracking.weighted_pe != null ? `${formatFinancial(tracking.weighted_pe, 1)}x` : "-"}</td>
                      <td style={{ color: (tracking.weighted_return_1d || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>{fmtPct(tracking.weighted_return_1d)}</td>
                      <td style={{ color: (tracking.weighted_return_1w || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>{fmtPct(tracking.weighted_return_1w)}</td>
                      <td style={{ color: (tracking.weighted_return_1m || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>{fmtPct(tracking.weighted_return_1m)}</td>
                      <td style={{ color: (tracking.weighted_return_3m || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>{fmtPct(tracking.weighted_return_3m)}</td>
                      <td style={{ color: (tracking.weighted_return_6m || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>{fmtPct(tracking.weighted_return_6m)}</td>
                      <td style={{ color: (tracking.weighted_return_1y || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>{fmtPct(tracking.weighted_return_1y)}</td>
                      <td style={{ color: (tracking.weighted_return_3y || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>{fmtPct(tracking.weighted_return_3y)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── EPS & 前瞻 PE 表格 ── */}
          {activeSection === "eps" && (
            <div className="card" style={{ marginTop: 8 }}>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>公司</th>
                      <th>EPS_TTM</th>
                      <th>EPS_2025</th>
                      <th>增速(估)</th>
                      <th>EPS_2026E</th>
                      <th>EPS_2027E</th>
                      <th>PE_2026E</th>
                      <th>PE_2027E</th>
                    </tr>
                  </thead>
                  <tbody>
                    {holdings.map((h, i) => (
                      <tr key={h.holding_id}>
                        <td>
                          <span style={{
                            display: "inline-block", width: 8, height: 8, borderRadius: "50%",
                            background: TICKER_COLORS[h.ticker] || COLORS[i % COLORS.length],
                            marginRight: 6,
                          }} />
                          <strong>{h.ticker}</strong>
                          <span style={{ color: "var(--text-secondary)", fontSize: 11, marginLeft: 4 }}>
                            {h.name_cn || h.company_name}
                          </span>
                        </td>
                        <td>{h.eps_ttm != null ? `$${fmt(h.eps_ttm, 2)}` : "-"}</td>
                        <td>{h.eps_2025 != null ? `$${fmt(h.eps_2025, 2)}` : "-"}</td>
                        <td>{h.growth_rate != null ? `${fmt(h.growth_rate, 0)}%` : "-"}</td>
                        <td>{h.eps_2026e != null ? `$${fmt(h.eps_2026e, 2)}` : "-"}</td>
                        <td>{h.eps_2027e != null ? `$${fmt(h.eps_2027e, 2)}` : "-"}</td>
                        <td>{h.forward_pe_2026e != null ? fmt(h.forward_pe_2026e, 1) : "-"}</td>
                        <td>{h.forward_pe_2027e != null ? fmt(h.forward_pe_2027e, 1) : "-"}</td>
                      </tr>
                    ))}
                    {/* 组合加权行 */}
                    <tr style={{ fontWeight: 700, background: "rgba(255,255,255,0.04)", borderTop: "2px solid var(--accent-blue)" }}>
                      <td><span style={{ color: "var(--accent-blue)" }}>组合加权</span></td>
                      <td>{tracking.weighted_eps_ttm != null ? `$${fmt(tracking.weighted_eps_ttm, 2)}` : "-"}</td>
                      <td>-</td>
                      <td>-</td>
                      <td>{tracking.weighted_eps_2026e != null ? `$${fmt(tracking.weighted_eps_2026e, 2)}` : "-"}</td>
                      <td>{tracking.weighted_eps_2027e != null ? `$${fmt(tracking.weighted_eps_2027e, 2)}` : "-"}</td>
                      <td>{tracking.weighted_forward_pe_2026e != null ? fmt(tracking.weighted_forward_pe_2026e, 1) : "-"}</td>
                      <td>{tracking.weighted_forward_pe_2027e != null ? fmt(tracking.weighted_forward_pe_2027e, 1) : "-"}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div style={{ marginTop: 8, padding: "8px 12px", background: "rgba(59,130,246,0.08)", borderRadius: 6, fontSize: 12, color: "var(--text-secondary)" }}>
                EPS增速 = EPS_TTM/EPS_2025 - 1（基于实际财务数据）；无 FY2025 数据的公司默认 15%。前瞻 EPS 采用时间加权复利，自当前日期至各年底剩余月份。EPS_TTM = 当前价/PE_TTM；2025年EPS = FY2025净利润 ÷ 总股本。加权按各持仓当前目标权重计算。
              </div>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}

export default PortfolioPage;
