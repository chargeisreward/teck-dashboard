import { useState, useEffect } from "react";
import {
  getPortfolios, getPortfolioHoldings, getPortfolioPerformance, getPortfolioEvaluations, evaluatePortfolio,
} from "../api";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell,
} from "recharts";

const COLORS = ["#3b82f6", "#22c55e", "#a855f7", "#f97316", "#ef4444", "#06b6d4", "#f59e0b"];

function PortfolioPage() {
  const [portfolios, setPortfolios] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [holdings, setHoldings] = useState([]);
  const [performance, setPerformance] = useState([]);
  const [evaluations, setEvaluations] = useState([]);
  const [evaluating, setEvaluating] = useState(false);
  const [evalResult, setEvalResult] = useState(null);
  const [activeTab, setActiveTab] = useState("holdings");

  useEffect(() => {
    getPortfolios().then((ps) => {
      setPortfolios(ps);
      if (ps.length > 0) setSelectedId(ps[0].id);
    });
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    getPortfolioHoldings(selectedId).then(setHoldings);
    getPortfolioPerformance(selectedId, 60).then(setPerformance);
    getPortfolioEvaluations(selectedId).then(setEvaluations);
    setEvalResult(null);
  }, [selectedId]);

  const handleEvaluate = async () => {
    setEvaluating(true);
    try {
      const result = await evaluatePortfolio(selectedId);
      setEvalResult(result);
      const evals = await getPortfolioEvaluations(selectedId);
      setEvaluations(evals);
    } finally {
      setEvaluating(false);
    }
  };

  const portfolio = portfolios.find((p) => p.id === selectedId);
  const perfData = [...performance].sort((a, b) => new Date(a.date) - new Date(b.date));
  const latestPerf = performance.length > 0 ? performance[0] : null;

  const pieData = holdings.map((h) => ({
    name: h.company?.ticker || "未知",
    value: h.actual_weight || h.weight,
  }));

  return (
    <div>
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h2>模拟组合</h2>
          <p>基于量化评分选出的龙头标的投资组合</p>
        </div>
        {portfolios.length > 0 && (
          <div style={{ display: "flex", gap: 8 }}>
            <select value={selectedId || ""}
              onChange={(e) => setSelectedId(Number(e.target.value))}
              style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff" }}>
              {portfolios.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <button onClick={handleEvaluate} disabled={evaluating}
              style={{ padding: "8px 20px", borderRadius: 8, border: "none", background: "var(--accent-blue)", color: "#fff", cursor: "pointer" }}>
              {evaluating ? "评估中..." : "评估组合"}
            </button>
          </div>
        )}
      </div>

      {portfolio && (
        <>
          {/* 组合概览 */}
          <div className="stats-grid">
            <div className="stat-card">
              <div className="label">最新市值</div>
              <div className="value blue" style={{ fontSize: 22 }}>${latestPerf?.total_value?.toLocaleString() || "-"}</div>
            </div>
            <div className="stat-card">
              <div className="label">累计收益</div>
              <div className="value" style={{ fontSize: 22, color: (latestPerf?.cumulative_return || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>
                {latestPerf?.cumulative_return ? `${latestPerf.cumulative_return >= 0 ? "+" : ""}${latestPerf.cumulative_return}%` : "-"}
              </div>
            </div>
            <div className="stat-card">
              <div className="label">夏普比率</div>
              <div className="value purple" style={{ fontSize: 22 }}>{latestPerf?.sharpe_ratio || "-"}</div>
            </div>
            <div className="stat-card">
              <div className="label">最大回撤</div>
              <div className="value orange" style={{ fontSize: 22 }}>{latestPerf?.max_drawdown ? `-${latestPerf.max_drawdown}%` : "-"}</div>
            </div>
          </div>

          {/* 图表区域 */}
          <div className="chart-grid">
            <div className="card chart-full">
              <h3>组合净值走势</h3>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={perfData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey={(d) => d.date?.slice(5)} stroke="#94a3b8" fontSize={12} />
                  <YAxis stroke="#94a3b8" fontSize={12} />
                  <Tooltip
                    contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                  />
                  <Line type="monotone" dataKey="total_value" stroke="#3b82f6" strokeWidth={2} dot={false} name="市值" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="card">
              <h3>持仓分布</h3>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, value }) => `${name} ${value}%`}>
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="card">
              <h3>累计收益 vs 基准</h3>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={perfData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey={(d) => d.date?.slice(5)} stroke="#94a3b8" fontSize={12} />
                  <YAxis stroke="#94a3b8" fontSize={12} />
                  <Tooltip
                    contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                  />
                  <Line type="monotone" dataKey="cumulative_return" stroke="#22c55e" strokeWidth={2} dot={false} name="组合收益%" />
                  <Line type="monotone" dataKey="benchmark_return" stroke="#94a3b8" strokeWidth={2} dot={false} name="基准%" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Tab: 持仓 / 评价 */}
          <div className="filter-bar" style={{ marginTop: 8 }}>
            <button className={activeTab === "holdings" ? "active" : ""} onClick={() => setActiveTab("holdings")}>持仓明细</button>
            <button className={activeTab === "evaluations" ? "active" : ""} onClick={() => setActiveTab("evaluations")}>
              评价记录 ({evaluations.length})
            </button>
          </div>

          {activeTab === "holdings" && (
            <div className="card">
              <h3>持仓明细</h3>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>公司</th>
                      <th>目标权重</th>
                      <th>实际权重</th>
                      <th>持股数</th>
                      <th>均价</th>
                      <th>现价</th>
                      <th>市值</th>
                      <th>收益率</th>
                      <th>配置理由</th>
                    </tr>
                  </thead>
                  <tbody>
                    {holdings.map((h) => (
                      <tr key={h.id}>
                        <td><strong>{h.company?.name_cn || h.company?.name}</strong>{h.company?.ticker ? <span style={{ color: "var(--text-secondary)", fontSize: 11, marginLeft: 4 }}>{h.company.ticker}</span> : null}</td>
                        <td>{h.weight}%</td>
                        <td>{h.actual_weight}%</td>
                        <td>{h.shares?.toLocaleString() || "-"}</td>
                        <td>${h.avg_cost || "-"}</td>
                        <td>${h.current_price || "-"}</td>
                        <td>${h.market_value?.toLocaleString() || "-"}</td>
                        <td style={{ color: (h.return_pct || 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>
                          {h.return_pct ? `${h.return_pct >= 0 ? "+" : ""}${h.return_pct}%` : "-"}
                        </td>
                        <td style={{ fontSize: 12, color: "var(--text-secondary)" }}>{h.allocation_reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === "evaluations" && (
            <div>
              {evalResult && (
                <div className="card" style={{ marginBottom: 16, borderLeft: "4px solid var(--accent-blue)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                    <h3>最新评估结果</h3>
                    <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>自动生成</span>
                  </div>
                  <p style={{ marginBottom: 8 }}>{evalResult.summary}</p>
                  {evalResult.adjustment_suggestion && (
                    <div style={{ padding: "8px 12px", background: "rgba(34,197,94,0.1)", borderRadius: 6, marginBottom: 8 }}>
                      <span style={{ fontSize: 12, color: "var(--accent-green)", fontWeight: 600 }}>调整建议: </span>
                      {evalResult.adjustment_suggestion}
                    </div>
                  )}
                  {evalResult.risk_warnings && (
                    <div style={{ padding: "8px 12px", background: "rgba(239,68,68,0.1)", borderRadius: 6 }}>
                      <span style={{ fontSize: 12, color: "var(--accent-red)", fontWeight: 600 }}>风险警告: </span>
                      {evalResult.risk_warnings}
                    </div>
                  )}
                </div>
              )}
              {evaluations.map((ev) => (
                <div key={ev.id} className="card" style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontWeight: 600 }}>{ev.date} 评估</span>
                    {ev.is_actionable && <span className="badge badge-red">需关注</span>}
                  </div>
                  <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 8 }}>{ev.summary}</p>
                  {ev.adjustment_suggestion && <p style={{ fontSize: 13 }}>建议: {ev.adjustment_suggestion}</p>}
                  {ev.risk_warnings && <p style={{ fontSize: 13, color: "var(--accent-red)" }}>风险: {ev.risk_warnings}</p>}
                </div>
              ))}
              {evaluations.length === 0 && <p style={{ color: "var(--text-secondary)", textAlign: "center", padding: 20 }}>暂无评价记录</p>}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default PortfolioPage;
