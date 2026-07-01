import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, CartesianGrid,
} from "recharts";
import { getDashboardOverview, getMarketData, refreshFollowPrices } from "../api";
import PriceTicker from "../components/PriceTicker";
import HotStocksPanel from "../components/HotStocksPanel";
import { formatFinancial } from "../utils/formatNumber";
import { EmptyState } from "../components/ui";

const COLORS = ["#3b82f6", "#22c55e", "#a855f7", "#f97316", "#ef4444", "#06b6d4", "#f59e0b", "#ec4899"];

function fmtNum(n) {
  if (n == null || isNaN(n)) return "-";
  if (Math.abs(n) >= 1000) return Math.round(n).toLocaleString();
  return Number.isInteger(n) ? n.toString() : n.toFixed(1);
}

function fmtPct(n) {
  if (n == null || isNaN(n)) return "-";
  const s = n >= 0 ? "+" : "";
  return `${s}${n.toFixed(2)}%`;
}

function Dashboard() {
  const [overview, setOverview] = useState(null);
  const [marketHistory, setMarketHistory] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      try {
        const data = await getDashboardOverview();
        if (!cancelled) setOverview(data);
        const hist = await getMarketData(null, 90);
        if (!cancelled) setMarketHistory(hist || []);
        if (!cancelled) setLastUpdated(new Date());
      } catch (e) {
        console.warn("Dashboard fetch failed:", e);
      }
    };
    fetchData();

    // 15 分钟自动刷新
    const interval = setInterval(async () => {
      try {
        await refreshFollowPrices();
        const data = await getDashboardOverview();
        if (!cancelled) setOverview(data);
        if (!cancelled) setLastUpdated(new Date());
      } catch (e) {
        console.warn("Auto-refresh failed:", e);
      }
    }, 15 * 60 * 1000);

    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  if (!overview) return <div className="loading">加载中...</div>;

  const coreCompanyIds = new Set(overview.core_companies.map((c) => c.id));
  const companyMap = {};
  overview.core_companies.forEach((c) => { companyMap[c.id] = c.ticker || c.name; });

  // 涨跌幅走势：仅核心公司
  const priceSeries = {};
  marketHistory.forEach((m) => {
    if (!coreCompanyIds.has(m.company_id)) return;
    if (!priceSeries[m.date]) priceSeries[m.date] = {};
    priceSeries[m.date][m.company_id] = m.stock_price;
  });

  const sortedDates = Object.keys(priceSeries).sort();
  const basePrices = {};
  overview.core_companies.forEach((c) => {
    for (const date of sortedDates) {
      if (priceSeries[date][c.id] != null) {
        basePrices[c.id] = priceSeries[date][c.id];
        break;
      }
    }
  });

  const lineChartData = sortedDates.map((date) => {
    const row = { date: date.slice(5) };
    Object.entries(priceSeries[date]).forEach(([cidStr, price]) => {
      const cid = parseInt(cidStr);
      const base = basePrices[cid];
      const ticker = companyMap[cid] || cid;
      if (base) {
        row[ticker] = parseFloat((((price - base) / base) * 100).toFixed(2));
      }
    });
    return row;
  });

  const yTickFormatter = (val) => `${val}%`;

  // 核心公司市值图数据
  const mcapData = overview.core_companies
    .filter((c) => c.market_cap_b != null)
    .map((c) => ({ name: c.ticker || c.name, cap: c.market_cap_b }));

  const timeStr = lastUpdated
    ? `${lastUpdated.getHours().toString().padStart(2, "0")}:${lastUpdated.getMinutes().toString().padStart(2, "0")}`
    : "";

  return (
    <div>
      <div className="page-header">
        <h2>市场概览</h2>
        <p>AI 芯片与半导体存储行业全景</p>
      </div>

      {/* 产业链卡片网格 */}
      <div className="chain-cards-grid">
        {overview.industry_chains.map((chain) => (
          <div key={chain.company_type} className="chain-card">
            <div className="chain-card-header">
              <span className="chain-card-name">{chain.name_cn}</span>
              <span className="chain-card-count">{chain.company_count} 家公司</span>
            </div>
            <div className="chain-card-metrics">
              {chain.avg_change_pct != null && (
                <div className="chain-card-metric">
                  <span className="metric-label">当日平均涨跌</span>
                  <span className={`metric-value font-numeric ${chain.avg_change_pct >= 0 ? "up" : "down"}`}>
                    {chain.avg_change_pct >= 0 ? "+" : ""}{chain.avg_change_pct}%
                  </span>
                </div>
              )}
              {chain.total_market_cap != null && (
                <div className="chain-card-metric">
                  <span className="metric-label">估值合计</span>
                  <span className="metric-value font-numeric">${formatFinancial(chain.total_market_cap, 0)}亿</span>
                </div>
              )}
              {chain.total_revenue_ttm != null && (
                <div className="chain-card-metric">
                  <span className="metric-label">TTM 营收合计</span>
                  <span className="metric-value font-numeric">${formatFinancial(chain.total_revenue_ttm, 0)}亿</span>
                </div>
              )}
              {chain.total_net_income_ttm != null && (
                <div className="chain-card-metric">
                  <span className="metric-label">TTM 利润合计</span>
                  <span className="metric-value font-numeric">${formatFinancial(chain.total_net_income_ttm, 0)}亿</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 核心公司实时价格 */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>核心公司实时价格</h3>
          <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
            {timeStr ? `最后更新: ${timeStr}` : "数据延迟约15分钟"}
          </span>
        </div>
        {overview.core_companies.length === 0 ? (
          <EmptyState
            icon="portfolio"
            title="尚未关注任何公司"
            description="请在「产业链全景」或「公司列表」页面关注最多 7 家公司作为核心公司"
          />
        ) : (
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {overview.core_companies.map((c) => (
              <PriceTicker key={c.id} ticker={c.ticker} nameCn={c.name_cn} compact />
            ))}
          </div>
        )}
      </div>

      <div className="chart-grid">
        <div className="card chart-full">
          <h3>涨跌幅走势（90 日）</h3>
          {overview.core_companies.length === 0 ? (
            <div style={{ height: 300, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-secondary)" }}>
              关注核心公司后展示涨跌幅走势
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={lineChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} tickFormatter={yTickFormatter} />
                <Tooltip
                  formatter={(val) => `${val}%`}
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                />
                {overview.core_companies.map((c, i) => (
                  <Line
                    key={c.id}
                    type="monotone"
                    dataKey={c.ticker || c.name}
                    stroke={COLORS[i % COLORS.length]}
                    strokeWidth={2}
                    dot={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card">
          <h3>核心公司市值（亿）</h3>
          {mcapData.length === 0 ? (
            <div style={{ height: 300, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-secondary)" }}>
              暂无市值数据
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={mcapData}>
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} />
                <Tooltip
                  formatter={(val) => `${fmtNum(val)}亿`}
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                />
                <Bar dataKey="cap" radius={[4, 4, 0, 0]}>
                  {mcapData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card">
          <h3>追踪概览</h3>
          {overview.core_companies.length === 0 ? (
            <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-secondary)", fontSize: 14 }}>
              关注核心公司后展示涨跌幅追踪
            </div>
          ) : (
            <div className="table-container" style={{ maxHeight: 400, overflowY: "auto" }}>
              <table style={{ fontSize: 12 }}>
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
                  {overview.core_companies.map((c) => (
                    <tr key={c.id}>
                      <td><strong>{c.ticker || c.name}</strong></td>
                      <td>{c.pe_ttm != null ? c.pe_ttm.toFixed(2) : "-"}</td>
                      <td className={c.change_pct >= 0 ? "up" : "down"}>{fmtPct(c.change_pct)}</td>
                      <td className={c.chg_1w >= 0 ? "up" : "down"}>{fmtPct(c.chg_1w)}</td>
                      <td className={c.chg_1m >= 0 ? "up" : "down"}>{fmtPct(c.chg_1m)}</td>
                      <td className={c.chg_3m >= 0 ? "up" : "down"}>{fmtPct(c.chg_3m)}</td>
                      <td className={c.chg_6m >= 0 ? "up" : "down"}>{fmtPct(c.chg_6m)}</td>
                      <td className={c.chg_1y >= 0 ? "up" : "down"}>{fmtPct(c.chg_1y)}</td>
                      <td className={c.chg_3y >= 0 ? "up" : "down"}>{fmtPct(c.chg_3y)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* A股热点榜 */}
      <HotStocksPanel />

      {/* 数据来源 */}
      <div style={{ marginTop: 20, padding: "12px 16px", fontSize: 11, color: "var(--text-secondary)", background: "rgba(255,255,255,0.02)", borderRadius: 8, lineHeight: 1.8 }}>
        <strong>数据来源：</strong><br/>
        实时价格/涨跌幅: 腾讯财经 API · 市值/PE: 基于腾讯财经实时行情（数据延迟约 15 分钟）<br/>
        市场规模: Gartner、TrendForce、Yole Group、SEMI、IDC 等权威产业研究机构公开报告<br/>
        产业链分类与公司基础数据: 内部数据库，最后更新 2026年6月
      </div>
    </div>
  );
}

export default Dashboard;
