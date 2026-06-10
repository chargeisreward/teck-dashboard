import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, LineChart, Line, CartesianGrid,
} from "recharts";
import { getDashboardSummary, getMarketData, getCompanies } from "../api";
import PriceTicker from "../components/PriceTicker";
import HotStocksPanel from "../components/HotStocksPanel";

const COLORS = ["#3b82f6", "#22c55e", "#a855f7", "#f97316", "#ef4444", "#06b6d4", "#f59e0b", "#ec4899"];

// 核心展示公司
const KEY_COMPANIES = [
  { ticker: "NVDA", nameCn: "英伟达" },
  { ticker: "TSM", nameCn: "台积电" },
  { ticker: "000660", nameCn: "SK海力士" },
  { ticker: "ASML", nameCn: "阿斯麦" },
  { ticker: "AVGO", nameCn: "博通" },
  { ticker: "MU", nameCn: "美光" },
];

function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [marketHistory, setMarketHistory] = useState([]);
  const [companies, setCompanies] = useState([]);

  useEffect(() => {
    getDashboardSummary().then(setSummary);
    getCompanies().then(setCompanies);
    getMarketData(null, 90).then(setMarketHistory);
  }, []);

  if (!summary) return <div className="loading">加载中...</div>;

  const marketCapData = summary.latest_market_caps.map((d) => ({
    name: d.ticker,
    cap: d.market_cap,
    fullName: d.name,
  }));

  const categoryData = summary.product_categories.map((d) => ({
    name: d.category,
    value: d.count,
  }));

  // 构建各公司涨跌幅序列（相对首日）
  const companyMap = {};
  companies.forEach((c) => { companyMap[c.id] = c.ticker; });

  const priceSeries = {};
  marketHistory.forEach((m) => {
    if (!priceSeries[m.date]) priceSeries[m.date] = {};
    priceSeries[m.date][m.company_id] = m.stock_price;
  });

  // 找到每家公司第一个价格作为基准
  const sortedDates = Object.keys(priceSeries).sort();
  const basePrices = {};
  companies.forEach((c) => {
    for (const date of sortedDates) {
      if (priceSeries[date][c.id] != null) {
        basePrices[c.id] = priceSeries[date][c.id];
        break;
      }
    }
  });

  const lineChartData = sortedDates.map((date) => {
    const row = { date: date.slice(5) };
    Object.entries(priceSeries[date]).forEach(([cid, price]) => {
      const base = basePrices[parseInt(cid)];
      const ticker = companyMap[parseInt(cid)] || cid;
      if (base) {
        row[ticker] = parseFloat((((price - base) / base) * 100).toFixed(2));
      }
    });
    return row;
  });

  // Y轴刻度格式化为百分比
  const yTickFormatter = (val) => `${val}%`;

  return (
    <div>
      <div className="page-header">
        <h2>市场概览</h2>
        <p>AI 芯片与半导体存储行业全景</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="label">追踪公司数</div>
          <div className="value blue">{summary.total_companies}</div>
        </div>
        <div className="stat-card">
          <div className="label">AI / 芯片产品</div>
          <div className="value green">{summary.total_products}</div>
        </div>
        <div className="stat-card">
          <div className="label">存储产品</div>
          <div className="value purple">{summary.total_storage_products}</div>
        </div>
        <div className="stat-card">
          <div className="label">产品类别</div>
          <div className="value orange">{summary.product_categories.length}</div>
        </div>
      </div>

      {/* 实时价格卡片 */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>核心公司实时价格</h3>
          <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>数据延迟约15分钟</span>
        </div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {KEY_COMPANIES.map((c) => (
            <PriceTicker key={c.ticker} ticker={c.ticker} nameCn={c.nameCn} compact />
          ))}
        </div>
      </div>

      <div className="chart-grid">
        <div className="card chart-full">
          <h3>涨跌幅走势（90 日）</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={lineChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} tickFormatter={yTickFormatter} />
              <Tooltip
                formatter={(val) => `${val}%`}
                contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
              />
              {companies.map((c, i) => (
                <Line
                  key={c.id}
                  type="monotone"
                  dataKey={c.ticker}
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3>市值（十亿美元）</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={marketCapData}>
              <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} />
              <Tooltip
                formatter={(val) => `$${val}B`}
                contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
              />
              <Bar dataKey="cap" radius={[4, 4, 0, 0]}>
                {marketCapData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3>产品分类</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={categoryData}
                cx="50%"
                cy="50%"
                outerRadius={90}
                dataKey="value"
                label={({ name, value }) => `${name} (${value})`}
              >
                {categoryData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
              />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* A股热点榜 */}
      <HotStocksPanel />
    </div>
  );
}

export default Dashboard;
