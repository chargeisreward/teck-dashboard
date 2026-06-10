import { useState, useEffect } from "react";
import { getCompanyScores, getScoringDimensions } from "../api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, Legend } from "recharts";

const COLORS = ["#3b82f6", "#22c55e", "#a855f7", "#f97316", "#06b6d4", "#ef4444"];

const TYPE_COLORS = {
  chip_design: "#3b82f6", manufacturing: "#22c55e", memory: "#a855f7",
  packaging: "#f97316", equipment: "#06b6d4", eda: "#ec4899",
  llm: "#f59e0b", cloud: "#ef4444", application: "#14b8a6", networking: "#8b5cf6",
};

const TYPE_LABELS = {
  chip_design: "AI芯片设计", manufacturing: "晶圆制造", memory: "存储/HBM",
  packaging: "先进封装", equipment: "半导体设备", eda: "EDA/IP",
  llm: "大模型/AI", cloud: "云厂商", application: "应用厂商", networking: "网络互联",
};

function Scoring() {
  const [scores, setScores] = useState([]);
  const [dimensions, setDimensions] = useState([]);
  const [activeType, setActiveType] = useState(null);

  useEffect(() => {
    getCompanyScores().then(setScores);
    getScoringDimensions().then(setDimensions);
  }, []);

  if (scores.length === 0) return <div className="loading">加载评分数据...</div>;

  const filtered = activeType
    ? scores.filter((s) => s.company_type === activeType)
    : scores;

  // 总分排序柱状图
  const chartData = filtered.map((s) => ({
    name: s.ticker,
    fullName: s.name_cn || s.company_name,
    score: s.total_score,
  }));

  // 各维度评分详情（仅显示前6家公司）
  const top6 = filtered.slice(0, 6);
  const dimChartData = dimensions.map((d) => {
    const row = { name: d.name_cn || d.name };
    top6.forEach((s) => {
      const ds = s.dimension_scores.find((ds) => ds.dimension === (d.name_cn || d.name));
      row[s.ticker] = ds?.score || 0;
    });
    return row;
  });

  // 各类型的计数
  const typeCounts = {};
  scores.forEach((s) => {
    const t = s.company_type || "other";
    typeCounts[t] = (typeCounts[t] || 0) + 1;
  });

  return (
    <div>
      <div className="page-header">
        <h2>量化评分选股</h2>
        <p>基于估值合理性、营收增长、供需缺口、进入壁垒、利润率、市场地位的量化评分体系</p>
      </div>

      {/* 维度权重 */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3>评分维度与权重</h3>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          {dimensions.map((d) => (
            <div key={d.id} style={{ flex: 1, minWidth: 150, padding: 12, background: "rgba(255,255,255,0.03)", borderRadius: 8 }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>{d.name_cn || d.name}</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: "var(--accent-blue)" }}>{d.weight}%</div>
              <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{d.description}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 分类筛选 */}
      <div className="filter-bar" style={{ marginBottom: 16 }}>
        <button className={!activeType ? "active" : ""} onClick={() => setActiveType(null)}>
          全部 ({scores.length})
        </button>
        {Object.entries(TYPE_LABELS).map(([key, label]) => {
          const count = typeCounts[key] || 0;
          if (count === 0) return null;
          return (
            <button key={key} className={activeType === key ? "active" : ""}
              onClick={() => setActiveType(key)}
              style={activeType === key ? { background: TYPE_COLORS[key], borderColor: TYPE_COLORS[key] } : {}}>
              {label} ({count})
            </button>
          );
        })}
      </div>

      {/* 总分图表 */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3>综合评分排名</h3>
        <ResponsiveContainer width="100%" height={Math.max(200, filtered.length * 30)}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 60 }}>
            <XAxis type="number" stroke="#94a3b8" fontSize={12} domain={[0, 100]} />
            <YAxis type="category" dataKey="name" stroke="#94a3b8" fontSize={12} width={50} />
            <Tooltip
              formatter={(val, name, props) => [`${val}分`, props.payload.fullName]}
              contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
            />
            <Bar dataKey="score" radius={[0, 4, 4, 0]}>
              {chartData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 各维度对比 */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3>各维度评分明细（前6名）</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={dimChartData}>
            <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
            <YAxis stroke="#94a3b8" fontSize={12} domain={[0, 100]} />
            <Tooltip
              contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
            />
            <Legend />
            {top6.map((s, i) => (
              <Bar key={s.company_id} dataKey={s.ticker} fill={COLORS[i % COLORS.length]} radius={[2, 2, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 详细评分表 */}
      <div className="card">
        <h3>完整评分列表</h3>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>排名</th>
                <th>公司</th>
                <th>类型</th>
                <th>上市</th>
                <th>总分</th>
                {dimensions.map((d) => (
                  <th key={d.id}>{d.name_cn || d.name} ({d.weight}%)</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((s, idx) => (
                <tr key={s.company_id}>
                  <td>{idx + 1}</td>
                  <td><strong>{s.name_cn || s.company_name}</strong>{s.name_cn && s.company_name !== s.name_cn ? <span style={{ color: "var(--text-secondary)", fontSize: 11, marginLeft: 4 }}>({s.company_name})</span> : null}{s.ticker ? <span style={{ color: "var(--text-secondary)", fontSize: 12, marginLeft: 6 }}>{s.ticker}</span> : null}</td>
                  <td>
                    <span className="badge" style={{ background: `${TYPE_COLORS[s.company_type] || "#666"}22`, color: TYPE_COLORS[s.company_type] || "#666", fontSize: 11 }}>
                      {TYPE_LABELS[s.company_type] || s.company_type}
                    </span>
                  </td>
                  <td>{s.is_listed ? <span className="badge badge-green" style={{ fontSize: 11 }}>上市</span> : <span className="badge badge-orange" style={{ fontSize: 11 }}>未上市</span>}</td>
                  <td><span style={{ fontSize: 16, fontWeight: 700, color: "var(--accent-blue)" }}>{s.total_score}</span></td>
                  {dimensions.map((d) => {
                    const ds = s.dimension_scores.find(
                      (ds) => ds.dimension === (d.name_cn || d.name)
                    );
                    return (
                      <td key={d.id}>
                        <span style={{ color: ds?.score >= 70 ? "var(--accent-green)" : ds?.score >= 50 ? "var(--accent-orange)" : "var(--accent-red)" }}>
                          {ds?.score ?? "-"}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default Scoring;
