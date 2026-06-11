import { useState, useEffect } from "react";
import { getCompanies, getFollows, followCompany, unfollowCompany } from "../api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const COLORS = ["#3b82f6", "#22c55e", "#a855f7", "#f97316", "#ef4444", "#06b6d4", "#f59e0b", "#ec4899"];

const TYPE_LABELS = {
  chip_design: "AI芯片设计",
  manufacturing: "晶圆制造",
  memory: "存储/HBM",
  packaging: "先进封装",
  equipment: "半导体设备",
  eda: "EDA/IP",
  llm: "大模型/AI",
  cloud: "云厂商",
  application: "应用厂商",
  networking: "网络互联",
};

const TYPE_COLORS = {
  chip_design: "#3b82f6",
  manufacturing: "#22c55e",
  memory: "#a855f7",
  packaging: "#f97316",
  equipment: "#06b6d4",
  eda: "#ec4899",
  llm: "#f59e0b",
  cloud: "#ef4444",
  application: "#14b8a6",
  networking: "#8b5cf6",
};

function Companies() {
  const [companies, setCompanies] = useState([]);
  const [activeType, setActiveType] = useState(null);
  const [sortBy, setSortBy] = useState("name");
  const [follows, setFollows] = useState([]);
  const [followLoading, setFollowLoading] = useState({});

  useEffect(() => {
    getCompanies().then(setCompanies);
    getFollows().then((data) => setFollows(data || [])).catch(() => {});
  }, []);

  const isFollowed = (companyId) => follows.some((f) => f.company_id === companyId);

  const handleToggleFollow = async (companyId, e) => {
    e.stopPropagation();
    setFollowLoading((prev) => ({ ...prev, [companyId]: true }));
    try {
      if (isFollowed(companyId)) {
        await unfollowCompany(companyId);
        setFollows((prev) => prev.filter((f) => f.company_id !== companyId));
      } else {
        await followCompany(companyId);
        const updated = await getFollows();
        setFollows(updated || []);
      }
    } catch (err) {
      const msg = (err.message || "").toLowerCase();
      if (msg.includes("400")) alert("关注失败：最多关注 7 家公司");
      else if (msg.includes("409")) alert("该公司已被关注");
      else alert("操作失败，请重试");
    } finally {
      setFollowLoading((prev) => ({ ...prev, [companyId]: false }));
    }
  };

  if (companies.length === 0) return <div className="loading">加载中...</div>;

  const filtered = activeType
    ? companies.filter((c) => c.company_type === activeType)
    : companies;

  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === "revenue") return (b.revenue_2024 || 0) - (a.revenue_2024 || 0);
    if (sortBy === "name") return a.name.localeCompare(b.name);
    return 0;
  });

  // Stats
  const typeCounts = {};
  companies.forEach((c) => {
    const t = c.company_type || "other";
    typeCounts[t] = (typeCounts[t] || 0) + 1;
  });
  const chartData = Object.entries(typeCounts).map(([name, value]) => ({
    name: TYPE_LABELS[name] || name,
    value,
  }));

  const totalRev = companies.reduce((s, c) => s + (c.revenue_2024 || 0), 0);
  const listed = companies.filter((c) => c.is_listed);
  const unlisted = companies.filter((c) => !c.is_listed);

  return (
    <div>
      <div className="page-header">
        <h2>产业链全量公司库</h2>
        <p>
          {companies.length} 家公司（上市 {listed.length} 家，未上市 {unlisted.length} 家）
          · 覆盖 {Object.keys(typeCounts).length} 个产业链环节
          · 合计营收 ~${(totalRev / 100).toFixed(1)} 万亿
        </p>
      </div>

      {/* 统计卡片 */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="label">所有公司</div>
          <div className="value blue">{companies.length}</div>
        </div>
        <div className="stat-card">
          <div className="label">上市公司</div>
          <div className="value green">{listed.length}</div>
        </div>
        <div className="stat-card">
          <div className="label">未上市公司</div>
          <div className="value orange">{unlisted.length}</div>
        </div>
        <div className="stat-card">
          <div className="label">大模型/AI公司</div>
          <div className="value purple">{typeCounts.llm || 0}</div>
        </div>
        <div className="stat-card">
          <div className="label">云厂商</div>
          <div className="value" style={{ color: "#ef4444" }}>{typeCounts.cloud || 0}</div>
        </div>
        <div className="stat-card">
          <div className="label">芯片设计</div>
          <div className="value" style={{ color: "#3b82f6" }}>{typeCounts.chip_design || 0}</div>
        </div>
      </div>

      {/* 分类筛选 */}
      <div className="filter-bar">
        <button className={!activeType ? "active" : ""} onClick={() => setActiveType(null)}>
          全部 ({companies.length})
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

      {/* 排序 */}
      <div style={{ marginBottom: 16, display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>排序:</span>
        <button style={{ padding: "4px 12px", borderRadius: 6, border: "1px solid var(--border)", background: sortBy === "name" ? "var(--accent-blue)" : "transparent", color: "#fff", cursor: "pointer", fontSize: 12 }}
          onClick={() => setSortBy("name")}>名称</button>
        <button style={{ padding: "4px 12px", borderRadius: 6, border: "1px solid var(--border)", background: sortBy === "revenue" ? "var(--accent-blue)" : "transparent", color: "#fff", cursor: "pointer", fontSize: 12 }}
          onClick={() => setSortBy("revenue")}>营收 ↓</button>
      </div>

      {/* 全量公司表格 */}
      <div className="card">
        <div className="table-container" style={{ maxHeight: 600, overflowY: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>公司</th>
                <th>关注</th>
                <th>类型</th>
                <th>领域</th>
                <th>上市</th>
                <th>2024营收(亿$)</th>
                <th>员工数</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((c) => (
                <tr key={c.id}>
                  <td>
                    <strong>{c.name_cn || c.name}</strong>
                    {c.name_cn && c.name !== c.name_cn && <span style={{ color: "var(--text-secondary)", fontSize: 11, marginLeft: 6 }}>({c.name})</span>}
                    {c.ticker && <span style={{ color: "var(--text-secondary)", fontSize: 12, marginLeft: 6 }}>{c.ticker}</span>}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <button
                      onClick={(e) => handleToggleFollow(c.id, e)}
                      disabled={followLoading[c.id]}
                      className={`follow-btn ${isFollowed(c.id) ? "followed" : ""}`}
                      title={isFollowed(c.id) ? "取消关注" : "添加为核心公司"}
                    >
                      {followLoading[c.id] ? "..." : isFollowed(c.id) ? "已关注" : "+ 关注"}
                    </button>
                  </td>
                  <td>
                    <span className="badge" style={{ background: `${TYPE_COLORS[c.company_type] || "#666"}22`, color: TYPE_COLORS[c.company_type] || "#666" }}>
                      {TYPE_LABELS[c.company_type] || c.company_type}
                    </span>
                  </td>
                  <td style={{ fontSize: 12, color: "var(--text-secondary)" }}>{c.sector}</td>
                  <td>{c.is_listed ? <span className="badge badge-green">上市</span> : <span className="badge badge-orange">未上市</span>}</td>
                  <td style={{ fontWeight: c.revenue_2024 > 100 ? 600 : 400 }}>
                    {c.revenue_2024 ? `$${c.revenue_2024}亿` : "-"}
                  </td>
                  <td style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                    {c.employee_count ? c.employee_count.toLocaleString() : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default Companies;
