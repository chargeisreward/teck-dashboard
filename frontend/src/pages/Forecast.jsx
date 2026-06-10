import { useState, useEffect } from "react";
import { getCompanies, getCompanyForecasts, getCompanyFinancials } from "../api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const COLORS = ["#3b82f6", "#22c55e", "#a855f7", "#f97316"];

function Forecast() {
  const [companies, setCompanies] = useState([]);
  const [forecasts, setForecasts] = useState({});
  const [financials, setFinancials] = useState({});

  useEffect(() => {
    getCompanies().then(async (comps) => {
      setCompanies(comps);
      const fcMap = {};
      const finMap = {};
      for (const c of comps) {
        const fcs = await getCompanyForecasts(c.id);
        if (fcs.length > 0) fcMap[c.id] = fcs;
        const fins = await getCompanyFinancials(c.id);
        if (fins.length > 0) finMap[c.id] = fins;
      }
      setForecasts(fcMap);
      setFinancials(finMap);
    });
  }, []);

  if (companies.length === 0) return <div className="loading">加载预测数据...</div>;

  // 只显示有预测的公司
  const forecastCompanies = companies.filter((c) => forecasts[c.id]?.length > 0);

  const revenueChartData = forecastCompanies.map((c) => {
    const fc = forecasts[c.id];
    const latestFin = financials[c.id]?.sort((a, b) => b.fiscal_year - a.fiscal_year)?.[0];
    const fc2026 = fc.find((f) => f.target_year === 2026);
    const fc2027 = fc.find((f) => f.target_year === 2027);
    return {
      name: c.ticker,
      latestRev: latestFin?.revenue || 0,
      rev2026: fc2026?.revenue_est || 0,
      rev2027: fc2027?.revenue_est || 0,
    };
  });

  return (
    <div>
      <div className="page-header">
        <h2>盈利预测与供需展望</h2>
        <p>2026E - 2027E 龙头公司收入、估值及供需平衡判断</p>
      </div>

      {/* 营收预测图表 */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3>营收预测（最新 vs 2026E vs 2027E，亿美元）</h3>
        <ResponsiveContainer width="100%" height={350}>
          <BarChart data={revenueChartData}>
            <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
            <YAxis stroke="#94a3b8" fontSize={12} />
            <Tooltip
              contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
            />
            <Bar dataKey="latestRev" name="最新" fill="#3b82f6" radius={[2, 2, 0, 0]} />
            <Bar dataKey="rev2026" name="2026E" fill="#22c55e" radius={[2, 2, 0, 0]} />
            <Bar dataKey="rev2027" name="2027E" fill="#a855f7" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 详细预测表格 */}
      {forecastCompanies.map((c) => {
        const fc = forecasts[c.id]?.sort((a, b) => a.target_year - b.target_year);
        if (!fc) return null;
        return (
          <div key={c.id} className="card" style={{ marginBottom: 16 }}>
            <h3 style={{ fontSize: 16, marginBottom: 12 }}>{c.name_cn || c.name}{c.ticker ? ` (${c.ticker})` : ""}</h3>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>预测年度</th>
                    <th>营收(亿$)</th>
                    <th>营收增长</th>
                    <th>PE</th>
                    <th>PS</th>
                    <th>市值预测(亿$)</th>
                    <th>置信度</th>
                    <th>分析师共识</th>
                  </tr>
                </thead>
                <tbody>
                  {fc.map((f) => (
                    <tr key={f.id}>
                      <td><strong>{f.target_year}E</strong></td>
                      <td>{f.revenue_est}</td>
                      <td style={{ color: "var(--accent-green)" }}>+{f.revenue_growth_est}%</td>
                      <td>{f.pe_est}</td>
                      <td>{f.ps_est}</td>
                      <td>{f.market_cap_est}</td>
                      <td><span className={`badge ${f.confidence === "高" ? "badge-green" : "badge-orange"}`}>{f.confidence}</span></td>
                      <td><span className={`badge ${f.analyst_consensus === "买入" ? "badge-green" : "badge-blue"}`}>{f.analyst_consensus}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {/* 供需平衡判断 */}
            {fc[0]?.supply_balance_note && (
              <div style={{ marginTop: 12, padding: 12, background: "rgba(255,255,255,0.03)", borderRadius: 8 }}>
                <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 4 }}>供需平衡判断</div>
                <div style={{ fontSize: 14, color: "var(--text-primary)" }}>{fc.map((f) => f.supply_balance_note).join(" | ")}</div>
              </div>
            )}
            {/* 风险 */}
            {fc[0]?.upside_risks && (
              <div style={{ marginTop: 8, display: "flex", gap: 16, fontSize: 13 }}>
                <div><span style={{ color: "var(--accent-green)" }}>上行风险:</span> {fc[0].upside_risks}</div>
                <div><span style={{ color: "var(--accent-red)" }}>下行风险:</span> {fc[0].downside_risks}</div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default Forecast;
