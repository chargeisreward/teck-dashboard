import { useState, useEffect, useCallback } from "react";
import { getIndustryOverview, getStockInfo, getPriceHistory, getCompanyFinancials, getFollows, followCompany, unfollowCompany } from "../api";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  BarChart, Bar, Cell,
} from "recharts";

const DIFFICULTY_COLORS = { "极高": "badge-red", "高": "badge-orange", "中": "badge-blue", "低": "badge-green" };
const CHART_COLORS = ["#3b82f6", "#22c55e", "#a855f7", "#f97316", "#ef4444", "#06b6d4", "#f59e0b", "#ec4899", "#14b8a6", "#8b5cf6"];
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

function formatPE(pe) {
  if (pe == null) return "-";
  if (pe < 0) return <span title="负收益（EPS < 0），PE无意义">N/A</span>;
  return `${pe.toFixed(1)}x`;
}

function formatMarketCap(v) {
  if (v == null) return "-";
  if (v >= 1e12) return `$${(v / 1e8).toFixed(0)}亿`;   // 1T = 10000亿
  if (v >= 1e8) return `$${(v / 1e8).toFixed(1)}亿`;    // 100M+ = 1亿+
  return `$${(v / 1e6).toFixed(0)}M`;                    // below 100M, keep M
}

// ── 实时价格卡片 ──────────────────────────────────────────────────

function CompanyPriceCard({ ticker, nameCn }) {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    getStockInfo(ticker).then(setInfo).catch(() => {}).finally(() => setLoading(false));
  }, [ticker]);

  // 每5分钟刷新价格数据
  useEffect(() => {
    if (!ticker) return;
    const interval = setInterval(() => {
      getStockInfo(ticker).then(setInfo).catch(() => {});
    }, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [ticker]);

  if (!ticker) return null;
  if (loading) return <div style={{ padding: 12, fontSize: 12, color: "var(--text-secondary)" }}>加载价格中...</div>;

  const price = info?.current_price_usd || info?.current_price;
  const changePct = info?.change_pct;
  const isUp = changePct != null && changePct >= 0;
  const dateStr = new Date().toISOString().slice(0, 10);

  return (
    <div style={{
      padding: "12px 16px", background: "rgba(255,255,255,0.03)", borderRadius: 8,
      border: "1px solid rgba(255,255,255,0.08)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>{nameCn}</div>
          <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>
            {ticker} · 数据日期 {dateStr}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          {price != null ? (
            <div style={{ fontSize: 24, fontWeight: 700 }}>${price.toFixed(2)}</div>
          ) : (
            <div style={{ fontSize: 14, color: "var(--text-secondary)" }}>-</div>
          )}
          {changePct != null && (
            <div style={{ fontSize: 13, fontWeight: 600, color: isUp ? "var(--accent-green)" : "var(--accent-red)" }}>
              {isUp ? "+" : ""}{changePct.toFixed(2)}%
            </div>
          )}
        </div>
      </div>
      {info && (
        <div style={{ display: "flex", gap: 16, marginTop: 8, fontSize: 11, color: "var(--text-secondary)", flexWrap: "wrap" }}>
          {info.pe_ttm != null && <span>PE(TTM): {info.pe_ttm.toFixed(1)}</span>}
          {info.market_cap != null && <span>市值: {formatMarketCap(info.market_cap)}</span>}
          {info.source && <span>来源: {info.source}</span>}
        </div>
      )}
    </div>
  );
}

// ── 价格走势图 ───────────────────────────────────────────────────

function PriceTrendChart({ ticker, nameCn }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    getPriceHistory(ticker, 1100)
      .then((d) => {
        const sorted = (d || []).sort((a, b) => new Date(a.date) - new Date(b.date));
        setData(sorted);
      })
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (!ticker) return null;
  if (loading) return <div style={{ padding: 20, textAlign: "center", fontSize: 12, color: "var(--text-secondary)" }}>加载走势中...</div>;
  if (data.length === 0) return <div style={{ padding: 20, textAlign: "center", fontSize: 12, color: "var(--text-secondary)" }}>暂无走势数据</div>;

  const firstPrice = data[0]?.price || 1;
  const lastPrice = data[data.length - 1]?.price;

  const chartData = data.map((d) => ({
    date: d.date.slice(5),
    price: d.price,
    pct: ((d.price - firstPrice) / firstPrice * 100),
  }));

  const isUp = lastPrice >= firstPrice;
  const lineColor = isUp ? "var(--accent-green)" : "var(--accent-red)";

  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 8 }}>
        {nameCn} · 近90日走势 · {isUp ? "+" : ""}{((lastPrice - firstPrice) / firstPrice * 100).toFixed(1)}%
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
          <YAxis domain={["dataMin - 5", "dataMax + 5"]} stroke="#94a3b8" fontSize={11} />
          <Tooltip
            formatter={(val, name) => [name === "pct" ? `${val.toFixed(2)}%` : `$${val.toFixed(2)}`, name === "pct" ? "涨跌幅" : "价格"]}
            contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
          />
          <Line type="monotone" dataKey="pct" stroke={lineColor} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── 市值比较 ─────────────────────────────────────────────────────

function MarketCapComparison({ ticker, peers }) {
  // peers: [{name_cn, ticker, market_cap}]
  const [infoMap, setInfoMap] = useState({});

  useEffect(() => {
    if (!ticker || !peers?.length) return;
    const allTickers = [...new Set([ticker, ...peers.map((p) => p.ticker).filter(Boolean)])];
    Promise.all(allTickers.map((t) => getStockInfo(t).then((d) => [t, d]).catch(() => [t, null]))).then((results) => {
      const m = {};
      results.forEach(([t, d]) => { m[t] = d; });
      setInfoMap(m);
    });
  }, [ticker, peers]);

  const chartData = [ticker, ...(peers?.map((p) => p.ticker).filter(Boolean) || [])]
    .filter((t) => infoMap[t]?.market_cap != null)
    .map((t) => ({
      ticker: t,
      name: infoMap[t]?.short_name || t,
      cap: infoMap[t].market_cap / 1e8,  // 转为亿
    }));

  if (chartData.length === 0) return null;

  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 8 }}>
        市值比较（亿美元）
      </div>
      <ResponsiveContainer width="100%" height={Math.max(150, chartData.length * 40)}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 20 }}>
          <XAxis type="number" stroke="#94a3b8" fontSize={11} />
          <YAxis type="category" dataKey="name" stroke="#94a3b8" fontSize={11} width={80} />
          <Tooltip formatter={(val) => `${val.toFixed(0)}亿`} contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }} />
          <Bar dataKey="cap" radius={[0, 4, 4, 0]}>
            {chartData.map((_, i) => (
              <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── 市占率比较 ──────────────────────────────────────────────────

function MarketShareComparison({ selectedTicker, peers }) {
  if (!peers?.length) return null;
  const selectedPeer = peers.find((p) => p.ticker === selectedTicker);
  if (!selectedPeer) return null;

  const chartData2 = peers
    .filter((p) => p.market_share != null)
    .map((p) => ({ name: p.name_cn || p.name, share: p.market_share, isSelected: p.ticker === selectedTicker }));

  if (chartData2.length === 0) return null;

  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 8 }}>
        产业链环节市占率比较（%）
        {selectedPeer.revenue_share != null && <span> · {selectedPeer.name_cn || selectedPeer.name} 收入占比: {selectedPeer.revenue_share}%</span>}
      </div>
      <ResponsiveContainer width="100%" height={Math.max(120, chartData2.length * 36)}>
        <BarChart data={chartData2} layout="vertical" margin={{ left: 20 }}>
          <XAxis type="number" stroke="#94a3b8" fontSize={11} unit="%" />
          <YAxis type="category" dataKey="name" stroke="#94a3b8" fontSize={11} width={90} />
          <Tooltip formatter={(val) => `${val}%`} contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }} />
          <Bar dataKey="share" radius={[0, 4, 4, 0]}>
            {chartData2.map((d, i) => (
              <Cell key={i} fill={d.isSelected ? "#f59e0b" : CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── 财务数据表 ──────────────────────────────────────────────────

function FinancialDataTable({ companyId }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (companyId == null) return;
    setLoading(true);
    getCompanyFinancials(companyId)
      .then((d) => setData(d || []))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [companyId]);

  if (companyId == null) return null;
  if (loading) return <div style={{ fontSize: 12, color: "var(--text-secondary)", textAlign: "center", padding: 12 }}>加载财务数据中...</div>;
  if (data.length === 0) return <div style={{ fontSize: 12, color: "var(--text-secondary)", textAlign: "center", padding: 12 }}>暂无财务数据</div>;

  // 行式展示: 每个指标一行, 各财年一列
  const fields = [
    { key: "revenue", label: "营收 (亿美元)", fmt: (v) => v != null ? `$${v.toFixed(1)}亿` : "-" },
    { key: "revenue_growth", label: "营收增长率", fmt: (v) => v != null ? `${v.toFixed(1)}%` : "-" },
    { key: "net_income", label: "净利润 (亿美元)", fmt: (v) => v != null ? `$${v.toFixed(1)}亿` : "-" },
    { key: "gross_margin", label: "毛利率", fmt: (v) => v != null ? `${v.toFixed(1)}%` : "-" },
    { key: "operating_margin", label: "营业利润率", fmt: (v) => v != null ? `${v.toFixed(1)}%` : "-" },
    { key: "net_margin", label: "净利率", fmt: (v) => v != null ? `${v.toFixed(1)}%` : "-" },
    { key: "eps", label: "每股收益 (EPS)", fmt: (v) => v != null ? `$${v.toFixed(2)}` : "-" },
    { key: "pe_ttm", label: "PE (TTM)", fmt: (v) => v != null ? `${v.toFixed(1)}x` : "-" },
    { key: "pe", label: "PE (年报)", fmt: (v) => v != null ? `${v.toFixed(1)}x` : "-" },
    { key: "pb", label: "PB", fmt: (v) => v != null ? `${v.toFixed(1)}x` : "-" },
    { key: "ps", label: "PS", fmt: (v) => v != null ? `${v.toFixed(1)}x` : "-" },
    { key: "ev_ebitda", label: "EV/EBITDA", fmt: (v) => v != null ? `${v.toFixed(1)}x` : "-" },
    { key: "roe", label: "ROE", fmt: (v) => v != null ? `${v.toFixed(1)}%` : "-" },
    { key: "debt_equity", label: "负债权益比", fmt: (v) => v != null ? `${v.toFixed(1)}%` : "-" },
    { key: "dividend_yield", label: "股息率", fmt: (v) => v != null ? `${v.toFixed(2)}%` : "-" },
  ];

  const years = data.sort((a, b) => b.fiscal_year - a.fiscal_year);

  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 8 }}>
        财务数据（单位：亿美元，除每股数据外）
      </div>
      <div className="table-container" style={{ maxHeight: 400, overflowY: "auto" }}>
        <table style={{ fontSize: 12 }}>
          <thead>
            <tr>
              <th style={{ position: "sticky", top: 0, background: "var(--card-bg)", zIndex: 1 }}>指标</th>
              {years.map((y) => (
                <th key={y.fiscal_year} style={{ position: "sticky", top: 0, background: "var(--card-bg)", zIndex: 1 }}>{y.fiscal_year}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {fields.map((f) => (
              <tr key={f.key}>
                <td style={{ fontWeight: 500, color: "var(--text-secondary)", whiteSpace: "nowrap" }}>{f.label}</td>
                {years.map((y) => (
                  <td key={y.fiscal_year} style={{ fontWeight: 600 }}>{f.fmt(y[f.key])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data[0]?.data_source && (
        <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 8, textAlign: "right" }}>
          数据来源: {data[0].data_source}
          {data[0].last_verified && <span> · 核实: {data[0].last_verified}</span>}
        </div>
      )}
    </div>
  );
}

// ── 主组件 ──────────────────────────────────────────────────────

function IndustryChain() {
  const [overview, setOverview] = useState([]);
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [peerCompanies, setPeerCompanies] = useState([]);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [follows, setFollows] = useState([]);
  const [followLoading, setFollowLoading] = useState({});

  useEffect(() => {
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

  const fetchData = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true);
    try {
      const data = await getIndustryOverview();
      setOverview(data);
      setLastUpdated(new Date());
    } catch (e) {
      console.warn("Industry overview fetch failed:", e);
    } finally {
      if (!silent) setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => fetchData(true), 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleCompanyClick = useCallback((company, chainCompanies) => {
    if (selectedCompany?.id === company.id) {
      setSelectedCompany(null);
      setPeerCompanies([]);
      return;
    }
    setSelectedCompany(company);
    // 过滤同一产业链公司的其它公司（用于同链比较）
    setPeerCompanies(chainCompanies.filter((c) => c.id !== company.id));
  }, [selectedCompany]);

  const companyHasTicker = (c) => c.ticker && c.ticker.match(/^[A-Z]/);

  if (overview.length === 0) return <div className="loading">加载产业链数据...</div>;

  return (
    <div>
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h2>产业链全景</h2>
            <p>AI 需求驱动的半导体产业链各环节深度分析 — 点击公司查看详情</p>
          </div>
          <div style={{ textAlign: "right", fontSize: 12, color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
            {lastUpdated && (
              <div>最后更新: {lastUpdated.toLocaleTimeString("zh-CN", { hour12: false })}</div>
            )}
            <button
              onClick={() => fetchData(false)}
              disabled={refreshing}
              style={{
                marginTop: 4, padding: "4px 12px", fontSize: 12, cursor: "pointer",
                background: refreshing ? "var(--bg-secondary)" : "var(--accent)",
                color: "#fff", border: "none", borderRadius: 4, opacity: refreshing ? 0.6 : 1,
              }}
            >
              {refreshing ? "刷新中..." : "刷新数据"}
            </button>
          </div>
        </div>
      </div>

      {/* ── 选中公司详情面板 ─────────────────────────────────── */}
      {selectedCompany && (
        <div className="card" style={{ marginBottom: 20, border: "1px solid var(--accent-blue)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 style={{ margin: 0, fontSize: 16 }}>
              {selectedCompany.name_cn || selectedCompany.name}
              <span style={{ fontWeight: 400, fontSize: 13, color: "var(--text-secondary)", marginLeft: 8 }}>
                {selectedCompany.ticker} · {TYPE_LABELS[selectedCompany.company_type] || selectedCompany.company_type}
              </span>
            </h3>
            <button
              onClick={() => { setSelectedCompany(null); setPeerCompanies([]); }}
              style={{ background: "transparent", border: "1px solid var(--border)", color: "var(--text-secondary)", padding: "4px 10px", borderRadius: 4, cursor: "pointer", fontSize: 12 }}
            >关闭</button>
          </div>

          {/* 第一行: 实时价格 + 走势图 */}
          <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 16, marginBottom: 16 }}>
            {companyHasTicker(selectedCompany) ? (
              <CompanyPriceCard ticker={selectedCompany.ticker} nameCn={selectedCompany.name_cn || selectedCompany.name} />
            ) : (
              <div style={{ padding: 12, fontSize: 12, color: "var(--text-secondary)", background: "rgba(255,255,255,0.03)", borderRadius: 8 }}>
                {selectedCompany.name_cn || selectedCompany.name} 未上市或无 ticker
              </div>
            )}
            {companyHasTicker(selectedCompany) ? (
              <PriceTrendChart ticker={selectedCompany.ticker} nameCn={selectedCompany.name_cn || selectedCompany.name} />
            ) : (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, color: "var(--text-secondary)", background: "rgba(255,255,255,0.03)", borderRadius: 8 }}>
                未上市企业暂无可比价格走势
              </div>
            )}
          </div>

          {/* 第二行: 市值比较 + 市占率比较 */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
            {companyHasTicker(selectedCompany) && peerCompanies.length > 0 && (
              <div style={{ padding: 12, background: "rgba(255,255,255,0.02)", borderRadius: 8, border: "1px solid rgba(255,255,255,0.05)" }}>
                <MarketCapComparison ticker={selectedCompany.ticker} peers={peerCompanies} />
              </div>
            )}
            {peerCompanies.length > 0 && (
              <div style={{ padding: 12, background: "rgba(255,255,255,0.02)", borderRadius: 8, border: "1px solid rgba(255,255,255,0.05)" }}>
                <MarketShareComparison selectedTicker={selectedCompany.ticker} peers={[selectedCompany, ...peerCompanies]} />
              </div>
            )}
          </div>

          {/* 第三行: 财务数据 */}
          <div style={{ padding: 12, background: "rgba(255,255,255,0.02)", borderRadius: 8, border: "1px solid rgba(255,255,255,0.05)" }}>
            <FinancialDataTable companyId={selectedCompany.id} />
          </div>
        </div>
      )}

      {/* ── 产业链各环节 ─────────────────────────────────────── */}
      {overview.map((seg) => {
        const ch = seg.chain;
        return (
          <div key={ch.id} className="card" style={{ marginBottom: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div>
                <h3 style={{ fontSize: 18, margin: 0, color: "var(--text-primary)" }}>{ch.name_cn || ch.name}</h3>
                <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>{ch.description}</span>
              </div>
              <span className={`badge ${DIFFICULTY_COLORS[ch.expansion_difficulty] || "badge-blue"}`}>
                扩产难度: {ch.expansion_difficulty}
              </span>
            </div>

            {/* 市场容量 */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
              <div className="stat-card" style={{ padding: 12 }}>
                <div className="label">2025 市场</div>
                <div className="value blue" style={{ fontSize: 20 }}>${(ch.market_size_2025 * 10).toFixed(0)}亿</div>
              </div>
              <div className="stat-card" style={{ padding: 12 }}>
                <div className="label">2026E 市场</div>
                <div className="value green" style={{ fontSize: 20 }}>${(ch.market_size_2026 * 10).toFixed(0)}亿</div>
              </div>
              <div className="stat-card" style={{ padding: 12 }}>
                <div className="label">2027E 市场</div>
                <div className="value purple" style={{ fontSize: 20 }}>${(ch.market_size_2027 * 10).toFixed(0)}亿</div>
              </div>
              <div className="stat-card" style={{ padding: 12 }}>
                <div className="label">CAGR</div>
                <div className="value orange" style={{ fontSize: 20 }}>{ch.growth_rate}%</div>
              </div>
            </div>
            {ch.data_source && (
              <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 12, padding: "6px 10px", background: "rgba(59,130,246,0.08)", borderRadius: 6, display: "inline-block" }}>
                数据来源: {ch.data_source}
                {ch.last_verified && <span> · 核实日期: {ch.last_verified}</span>}
              </div>
            )}

            {/* 供需缺口 */}
            <div style={{ marginBottom: 16 }}>
              <h4 style={{ fontSize: 14, color: "var(--accent-blue)", marginBottom: 8 }}>供需分析</h4>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                {["2025", "2026E", "2027E"].map((p) => {
                  const sd = seg.supply_demand?.find((s) => s.period === p);
                  return (
                    <div key={p} style={{ background: "rgba(255,255,255,0.03)", borderRadius: 8, padding: 12 }}>
                      <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>{p}</div>
                      {sd ? (
                        <>
                          <div style={{ fontSize: 13 }}>供给: {sd.supply} | 需求: {sd.demand}</div>
                          <div style={{ fontSize: 13, color: sd.gap_pct < 0 ? "var(--accent-red)" : "var(--accent-green)" }}>
                            缺口: {sd.gap_pct}%
                          </div>
                          <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                            产能利用率: {sd.capacity_utilization}% | 交期: {sd.lead_time_weeks}周
                          </div>
                        </>
                      ) : <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{ch[`supply_gap_${p.replace("E","")}`] || "-"}</div>}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 龙头供应商 (可点击) */}
            <div style={{ marginBottom: 16 }}>
              <h4 style={{ fontSize: 14, color: "var(--accent-blue)", marginBottom: 8 }}>
                主要供应商
                <span style={{ fontWeight: 400, fontSize: 11, color: "var(--text-secondary)", marginLeft: 8 }}>点击公司查看详情</span>
              </h4>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>公司</th>
                      <th>关注</th>
                      <th>类型</th>
                      <th>上市</th>
                      <th>PE(TTM)</th>
                      <th>2026E PE</th>
                      <th>2027E PE</th>
                      <th>2025营收(B)</th>
                      <th>市占率</th>
                      <th>收入占比</th>
                      <th>龙头</th>
                      <th>竞争优势</th>
                    </tr>
                  </thead>
                  <tbody>
                    {seg.companies.map((c) => {
                      const isSelected = selectedCompany?.id === c.id;
                      return (
                        <tr
                          key={c.id}
                          onClick={() => handleCompanyClick(c, seg.companies)}
                          style={{
                            cursor: "pointer",
                            background: isSelected ? "rgba(59,130,246,0.1)" : undefined,
                            transition: "background 0.15s",
                          }}
                          onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
                          onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = ""; }}
                        >
                          <td><strong>{c.name_cn || c.name}</strong>{c.name_cn && c.name !== c.name_cn ? <span style={{ color: "var(--text-secondary)", fontSize: 11, marginLeft: 4 }}>({c.name})</span> : null}{c.ticker ? <span style={{ color: "var(--text-secondary)", fontSize: 12, marginLeft: 6 }}>{c.ticker}</span> : null}</td>
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
                          <td>{c.is_listed ? <span className="badge badge-green">上市</span> : <span className="badge badge-orange">未上市</span>}</td>
                          <td style={{ fontWeight: c.pe_ttm ? 600 : 400, color: c.pe_ttm && c.pe_ttm > 0 ? "var(--text-primary)" : "var(--text-secondary)", fontSize: 13 }}>
                            {formatPE(c.pe_ttm)}
                            {c.pe_source === "tencent" && c.pe_ttm > 0 && <span style={{ fontSize: 10, color: "#22c55e", marginLeft: 4 }}>●</span>}
                          </td>
                          <td style={{ fontWeight: c.analyst_pe_2026 ? 600 : 400, color: "#22c55e", fontSize: 13 }}>
                            {c.analyst_pe_2026 ? `${c.analyst_pe_2026.toFixed(1)}x` : "-"}
                          </td>
                          <td style={{ fontWeight: c.analyst_pe_2027 ? 600 : 400, color: "#3b82f6", fontSize: 13 }}>
                            {c.analyst_pe_2027 ? `${c.analyst_pe_2027.toFixed(1)}x` : "-"}
                          </td>
                          <td style={{ fontWeight: c.revenue_2025_b ? 600 : 400, fontSize: 13 }}>
                            {c.revenue_2025_b ? `$${(c.revenue_2025_b * 10).toFixed(0)}亿` : "-"}
                            {c.revenue_source === "tencent" && <span style={{ fontSize: 10, color: "#22c55e", marginLeft: 4 }}>●</span>}
                          </td>
                          <td>{c.market_share}%{c.data_source ? <span style={{ fontSize: 10, color: "#3b82f6", marginLeft: 4, cursor: "help" }} title={c.data_source}>ⓘ</span> : null}</td>
                          <td>{c.revenue_share}%</td>
                          <td>{c.is_leader ? <span className="badge badge-green">龙头</span> : "—"}</td>
                          <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>{c.competitive_advantage}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 数据来源说明 */}
            <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 16, lineHeight: 1.6, padding: "8px 12px", background: "rgba(255,255,255,0.02)", borderRadius: 6 }}>
              <strong>数据来源：</strong><br/>
              <span style={{ color: "#3b82f6" }}>ⓘ</span> 市场规模: Gartner半导体排名 (2026.1)、TrendForce HBM报告、Yole先进封装行业报告、SEMI设备市场报告、IDC/Gartner AI服务器预测<br/>
              <span style={{ color: "#22c55e" }}>●</span> PE(TTM)/市值: 腾讯财经 API 实时行情（前复权）<br/>
              <span style={{ color: "#3b82f6" }}>ⓘ</span> 市占率: Gartner、Mercury Research、IC Insights、TrendForce、Yole Group、SEMI、Counterpoint、公司年报<br/>
              财务数据: Wind 金融终端（已采集 24 家上市公司 2025 年报数据）<br/>
              PE为负值（N/A）表示该企业报告期亏损。预测数据仅用于参考，不构成投资建议。
            </div>

            {/* 壁垒与驱动 */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <h4 style={{ fontSize: 14, color: "var(--accent-orange)", marginBottom: 4 }}>进入壁垒</h4>
                <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>{ch.entry_barriers}</p>
              </div>
              <div>
                <h4 style={{ fontSize: 14, color: "var(--accent-green)", marginBottom: 4 }}>增长驱动力</h4>
                <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>{ch.key_drivers}</p>
              </div>
              <div style={{ gridColumn: "1/-1" }}>
                <h4 style={{ fontSize: 14, color: "var(--accent-red)", marginBottom: 4 }}>风险因素</h4>
                <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>{ch.risks}</p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default IndustryChain;
