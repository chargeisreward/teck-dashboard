import { useState, useEffect, useMemo } from "react";
import { getPriceHistory, getStockInfo } from "../api";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Area, AreaChart,
} from "recharts";

const TICKERS = [
  { ticker: "TSM", name: "台积电 (TSM)", nameCn: "台积电 ADR", color: "#3b82f6" },
  { ticker: "000660.KS", name: "SK海力士", nameCn: "SK海力士", color: "#a855f7" },
  { ticker: "EWY", name: "iShares MSCI 韩国 ETF", nameCn: "韩国ETF (EWY)", color: "#22c55e" },
  { ticker: "AIA", name: "iShares 亚洲50 ETF", nameCn: "亚洲50ETF (AIA)", color: "#f59e0b" },
];

// EWY 前10大重仓 (iShares MSCI South Korea ETF)
const EWY_HOLDINGS = [
  { rank: 1, name: "SK Hynix", ticker: "000660.KS", weight: 28.5 },
  { rank: 2, name: "Samsung Electronics", ticker: "005930.KS", weight: 24.0 },
  { rank: 3, name: "Hyundai Motor", ticker: "005380.KS", weight: 4.2 },
  { rank: 4, name: "LG Energy Solution", ticker: "373220.KS", weight: 3.0 },
  { rank: 5, name: "KB Financial Group", ticker: "105560.KS", weight: 2.5 },
  { rank: 6, name: "POSCO Holdings", ticker: "005490.KS", weight: 2.2 },
  { rank: 7, name: "Shinhan Financial Group", ticker: "055550.KS", weight: 2.0 },
  { rank: 8, name: "NAVER Corp", ticker: "035420.KS", weight: 1.8 },
  { rank: 9, name: "Samsung SDI", ticker: "006400.KS", weight: 1.5 },
  { rank: 10, name: "LG Electronics", ticker: "066570.KS", weight: 1.3 },
];
const EWY_TOP10_TOTAL = EWY_HOLDINGS.reduce((s, h) => s + h.weight, 0);

// AIA 前10大重仓 (iShares Asia 50 ETF)
const AIA_HOLDINGS = [
  { rank: 1, name: "台积电 (TSMC)", ticker: "TSM", weight: 25.0 },
  { rank: 2, name: "Tencent Holdings", ticker: "TCEHY", weight: 12.0 },
  { rank: 3, name: "Samsung Electronics", ticker: "005930.KS", weight: 8.0 },
  { rank: 4, name: "Alibaba Group", ticker: "BABA", weight: 5.0 },
  { rank: 5, name: "MediaTek", ticker: "2454.TW", weight: 3.5 },
  { rank: 6, name: "SK Hynix", ticker: "000660.KS", weight: 3.5 },
  { rank: 7, name: "AIA Group", ticker: "1299.HK", weight: 3.0 },
  { rank: 8, name: "Meituan", ticker: "MPNGY", weight: 2.5 },
  { rank: 9, name: "China Construction Bank", ticker: "CICHY", weight: 2.0 },
  { rank: 10, name: "ICBC", ticker: "IDCBY", weight: 1.8 },
];
const AIA_TOP10_TOTAL = AIA_HOLDINGS.reduce((s, h) => s + h.weight, 0);

const EWY_SK_HYNIX_WEIGHT = EWY_HOLDINGS[0].weight;
const AIA_SK_HYNIX_WEIGHT = AIA_HOLDINGS[5].weight;

function formatCurrency(v) {
  if (v == null || isNaN(v)) return "-";
  if (v >= 1e12) return `$${(v / 1e8).toFixed(0)}亿`;    // 1T = 10000亿
  if (v >= 1e8) return `$${(v / 1e8).toFixed(1)}亿`;     // 100M+ = 1亿+
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  return `$${Number(v).toFixed(2)}`;
}

function formatLargeNumber(v) {
  if (v == null || isNaN(v)) return "-";
  return v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function PriceChart({ ticker, color, nameCn, days }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getPriceHistory(ticker, days)
      .then((d) => {
        const sorted = (d || []).sort((a, b) => new Date(a.date) - new Date(b.date));
        setData(sorted);
      })
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [ticker, days]);

  if (loading) return <div style={{ height: 160, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, color: "var(--text-secondary)" }}>加载中...</div>;
  if (data.length === 0) return <div style={{ height: 160, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, color: "var(--text-secondary)" }}>暂无价格数据（外部数据源不可用）</div>;

  const firstPrice = data[0]?.price || 1;
  const lastPrice = data[data.length - 1]?.price || 0;
  const pctChange = ((lastPrice - firstPrice) / firstPrice * 100).toFixed(1);
  const isPositive = parseFloat(pctChange) >= 0;

  const chartData = data.map((d) => ({
    date: d.date,
    price: d.price,
    pct: ((d.price - firstPrice) / firstPrice * 100),
  }));

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 4 }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{nameCn}</div>
          <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>{ticker}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontWeight: 700, fontSize: 16 }}>${lastPrice.toFixed(2)}</div>
          <div style={{ fontSize: 12, fontWeight: 600, color: isPositive ? "var(--accent-green)" : "var(--accent-red)" }}>
            {isPositive ? "+" : ""}{pctChange}%
          </div>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id={`grad-${ticker}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <XAxis dataKey="date" hide />
          <YAxis domain={["dataMin - 5", "dataMax + 5"]} hide />
          <Tooltip
            formatter={(val) => [`$${val.toFixed(2)}`, "价格"]}
            labelFormatter={(l) => `日期: ${l}`}
            contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
          />
          <Area type="monotone" dataKey="price" stroke={color} strokeWidth={2} fill={`url(#grad-${ticker})`} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function ValuationCard({ ticker, label, isEtf }) {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStockInfo(ticker).then(setInfo).catch(() => {}).finally(() => setLoading(false));
  }, [ticker]);

  return (
    <div style={{ padding: "8px 12px", background: "var(--card-bg)", borderRadius: 8, border: "1px solid var(--border)" }}>
      <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 2 }}>{label}</div>
      {loading ? (
        <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>加载中...</div>
      ) : isEtf ? (
        <>
          <div style={{ fontSize: 13, fontWeight: 600 }}>PE: -</div>
          <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>市值: -</div>
          <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 4 }}>ETF 查看下方重仓明细</div>
        </>
      ) : (
        <>
          <div style={{ fontSize: 13, fontWeight: 600 }}>
            PE: {info?.pe_ttm != null ? info.pe_ttm.toFixed(1) : "-"}
          </div>
          <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
            市值: {formatCurrency(info?.market_cap)}
          </div>
        </>
      )}
    </div>
  );
}

function HoldingsTable({ title, holdings, top10Total, skHynixWeight, skLabel }) {
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h3>{title}</h3>
      <p style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 8 }}>
        前10大重仓合计 <strong>{top10Total.toFixed(1)}%</strong>，
        {skLabel}占比 <strong style={{ color: "#a855f7" }}>{skHynixWeight.toFixed(1)}%</strong>
      </p>
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>名称</th>
              <th>Ticker</th>
              <th style={{ textAlign: "right" }}>权重</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => (
              <tr key={h.rank}>
                <td style={{ color: "var(--text-secondary)", fontSize: 12 }}>{h.rank}</td>
                <td style={{ fontWeight: h.name.includes("SK Hynix") || h.name.includes("海力士") ? 700 : 400 }}>
                  {h.name}
                  {(h.name.includes("SK Hynix") || h.name.includes("海力士")) && (
                    <span style={{ fontSize: 10, color: "#a855f7", marginLeft: 4 }}>HBM核心</span>
                  )}
                </td>
                <td style={{ fontSize: 12, color: "var(--text-secondary)" }}>{h.ticker}</td>
                <td style={{ textAlign: "right", fontWeight: 600 }}>{h.weight.toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const FORWARD_PE_TABLE = [
  { company: "台积电 (TSM)", ticker: "TSM", currentPE: "36.3", pe2026E: "27.5", pe2027E: "22.0" },
  { company: "SK海力士", ticker: "000660.KS", currentPE: "11.5", pe2026E: "8.5", pe2027E: "7.0" },
  { company: "iShares MSCI 韩国 ETF (EWY)", ticker: "EWY", currentPE: "ETF", pe2026E: "ETF", pe2027E: "ETF" },
  { company: "iShares 亚洲50 ETF (AIA)", ticker: "AIA", currentPE: "ETF", pe2026E: "ETF", pe2027E: "ETF" },
];

function InvestmentPlan() {
  const [priceDays, setPriceDays] = useState(365);

  return (
    <div>
      <div className="page-header">
        <h2>TSM + EWY 配置方案</h2>
        <p>AI 硬件核心资产组合：台积电 × SK海力士，约 2:1 敞口</p>
      </div>

      {/* 快速摘要 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          <div style={{ textAlign: "center", padding: 12 }}>
            <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 4 }}>推荐配置</div>
            <div style={{ fontWeight: 700, fontSize: 20, color: "#3b82f6" }}>40% TSM</div>
            <div style={{ fontWeight: 700, fontSize: 20, color: "#22c55e" }}>60% EWY</div>
          </div>
          <div style={{ textAlign: "center", padding: 12, borderLeft: "1px solid var(--border)", borderRight: "1px solid var(--border)" }}>
            <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 4 }}>核心敞口</div>
            <div style={{ fontWeight: 700, fontSize: 20 }}>TSMC ~40%</div>
            <div style={{ fontWeight: 700, fontSize: 20, color: "#a855f7" }}>SK海力士 ~16.8%</div>
          </div>
          <div style={{ textAlign: "center", padding: 12 }}>
            <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 4 }}>适合</div>
            <div style={{ fontSize: 13 }}>看好AI基础设施</div>
            <div style={{ fontSize: 13 }}>偏好大型基金公司</div>
            <div style={{ fontSize: 13 }}>避免过多中国资产</div>
          </div>
        </div>
      </div>

      {/* 价格走势 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ fontSize: 14, margin: 0 }}>价格走势</h3>
          <div style={{ display: "flex", gap: 4 }}>
            <button className={priceDays === 365 ? "active" : ""}
              onClick={() => setPriceDays(365)}
              style={{ padding: "2px 10px", fontSize: 11, borderRadius: 4, border: "1px solid var(--border)", cursor: "pointer", background: priceDays === 365 ? "var(--accent-blue)" : "transparent", color: priceDays === 365 ? "#fff" : "var(--text-primary)" }}>
              1年
            </button>
            <button className={priceDays === 1095 ? "active" : ""}
              onClick={() => setPriceDays(1095)}
              style={{ padding: "2px 10px", fontSize: 11, borderRadius: 4, border: "1px solid var(--border)", cursor: "pointer", background: priceDays === 1095 ? "var(--accent-blue)" : "transparent", color: priceDays === 1095 ? "#fff" : "var(--text-primary)" }}>
              3年
            </button>
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {TICKERS.map((t) => (
            <div key={t.ticker} className="chart-container" style={{ padding: 12, background: "var(--card-bg)", borderRadius: 8, border: "1px solid var(--border)" }}>
              <PriceChart ticker={t.ticker} color={t.color} nameCn={t.nameCn} days={priceDays} />
            </div>
          ))}
        </div>
      </div>

      {/* 投资逻辑 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>投资逻辑</h3>
        <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.7 }}>
          AI 产业链最核心的两个环节是 <strong>AI 算力制造</strong>（台积电）和 <strong>AI 算力内存</strong>（SK海力士）。
          几乎所有先进 AI 芯片（NVIDIA GPU、AMD GPU、Apple 芯片、Broadcom ASIC、Amazon Trainium、Google TPU）
          最终都在台积电制造。SK海力士则是 NVIDIA 最核心的 HBM 供应商。
        </p>
        <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.7 }}>
          直接配置 TSM + EWY 相比 AIA 的优势在于：AIA 前十大持仓包含腾讯、MediaTek、香港金融股等非 AI 硬件资产，
          更像亚洲大型股 ETF。而 TSM + EWY 组合纯度更高，基本避开中国互联网和金融权重。
        </p>
      </div>

      {/* 估值水平 */}
      <h3 style={{ fontSize: 14, marginBottom: 8 }}>估值水平</h3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 12, marginBottom: 16 }}>
        <ValuationCard ticker="TSM" label="台积电 (TSM)" />
        <ValuationCard ticker="000660.KS" label="SK海力士" />
        <ValuationCard ticker="EWY" label="iShares 韩国 ETF" isEtf={true} />
        <ValuationCard ticker="AIA" label="iShares 亚洲50 ETF" isEtf={true} />
      </div>

      {/* 预期估值表 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>估值水平与预期</h3>
        <p style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 8 }}>
          基于分析师一致预期数据的当前及未来 PE 估值
        </p>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>标的</th>
                <th>当前PE (TTM)</th>
                <th>2026E PE</th>
                <th>2027E PE</th>
                <th>估值扩张/收缩</th>
              </tr>
            </thead>
            <tbody>
              {FORWARD_PE_TABLE.map((row) => {
                const isEtf = row.pe2026E === "ETF";
                const cur = parseFloat(row.currentPE);
                const e2026 = parseFloat(row.pe2026E);
                const e2027 = parseFloat(row.pe2027E);
                const change26 = !isNaN(e2026) && !isNaN(cur) ? ((e2026 - cur) / cur * 100).toFixed(1) : null;
                const change27 = !isNaN(e2027) && !isNaN(cur) ? ((e2027 - cur) / cur * 100).toFixed(1) : null;
                return (
                  <tr key={row.ticker}>
                    <td style={{ fontWeight: 600 }}>{row.company}</td>
                    <td style={{ fontWeight: 700, fontSize: 14 }}>{row.currentPE}{isEtf ? "" : "x"}</td>
                    <td style={{ fontWeight: 600, fontSize: 14, color: "#22c55e" }}>{row.pe2026E}{isEtf ? "" : "x"}</td>
                    <td style={{ fontWeight: 600, fontSize: 14, color: "#3b82f6" }}>{row.pe2027E}{isEtf ? "" : "x"}</td>
                    <td>
                      {isEtf ? (
                        <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>ETF 无 PE</span>
                      ) : (
                        <>
                          <span style={{ fontSize: 12, color: "#22c55e" }}>2026E: {change26}%</span><br />
                          <span style={{ fontSize: 12, color: "#3b82f6" }}>2027E: {change27}%</span>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 8 }}>
          注：未来 PE 预期基于分析师一致估计。随着盈利增长，PE 通常会自然消化（收缩），这并不意味着股价下跌。
          SK海力士因 HBM 高利润周期，当前 PE 处于历史低位。
        </div>
      </div>

      {/* EWY 重仓 */}
      <HoldingsTable
        title="iShares MSCI 韩国 ETF (EWY) — 前10大重仓"
        holdings={EWY_HOLDINGS}
        top10Total={EWY_TOP10_TOTAL}
        skHynixWeight={EWY_SK_HYNIX_WEIGHT}
        skLabel="SK海力士"
      />

      {/* AIA 重仓 */}
      <HoldingsTable
        title="iShares 亚洲50 ETF (AIA) — 前10大重仓"
        holdings={AIA_HOLDINGS}
        top10Total={AIA_TOP10_TOTAL}
        skHynixWeight={AIA_SK_HYNIX_WEIGHT}
        skLabel="SK海力士"
      />

      {/* 配置方案 */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
        <div className="card">
          <h3>方案 A — 最接近 2:1 敞口</h3>
          <table style={{ width: "100%", fontSize: 13 }}>
            <thead>
              <tr><th>资产</th><th>配置</th><th>TSMC敞口</th><th>SK海力士敞口</th></tr>
            </thead>
            <tbody>
              <tr><td>TSM</td><td style={{ fontWeight: 700, color: "#3b82f6" }}>36%</td><td>36%</td><td>-</td></tr>
              <tr><td>EWY</td><td style={{ fontWeight: 700, color: "#22c55e" }}>64%</td><td>-</td><td>~18%</td></tr>
              <tr style={{ borderTop: "2px solid var(--border)" }}>
                <td style={{ fontWeight: 600 }}>合计</td><td>100%</td>
                <td style={{ fontWeight: 600, color: "#3b82f6" }}>36%</td>
                <td style={{ fontWeight: 600, color: "#a855f7" }}>~18%</td>
              </tr>
            </tbody>
          </table>
          <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 8 }}>
            比例 36:18 ≈ <strong>2:1</strong>
          </div>
        </div>

        <div className="card">
          <h3>方案 B — 推荐（更均衡）</h3>
          <table style={{ width: "100%", fontSize: 13 }}>
            <thead>
              <tr><th>资产</th><th>配置</th><th>TSMC敞口</th><th>SK海力士敞口</th></tr>
            </thead>
            <tbody>
              <tr><td>TSM</td><td style={{ fontWeight: 700, color: "#3b82f6" }}>40%</td><td>40%</td><td>-</td></tr>
              <tr><td>EWY</td><td style={{ fontWeight: 700, color: "#22c55e" }}>60%</td><td>-</td><td>~16.8%</td></tr>
              <tr style={{ borderTop: "2px solid var(--border)" }}>
                <td style={{ fontWeight: 600 }}>合计</td><td>100%</td>
                <td style={{ fontWeight: 600, color: "#3b82f6" }}>~40%</td>
                <td style={{ fontWeight: 600, color: "#a855f7" }}>~16.8%</td>
              </tr>
            </tbody>
          </table>
          <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 8 }}>
            同时获得三星 ~14.6%、现代汽车等韩国龙头敞口
          </div>
        </div>
      </div>

      {/* 风险分析 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>主要风险分析</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div style={{ padding: 12, background: "rgba(239,68,68,0.05)", borderRadius: 8, border: "1px solid rgba(239,68,68,0.15)" }}>
            <div style={{ fontWeight: 600, fontSize: 13, color: "#ef4444", marginBottom: 4 }}>台海风险</div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6 }}>
              最大尾部风险。市场长期给予TSMC一定地缘政治折价。海外扩产（美国、日本、德国）正在推进，但核心先进制程仍主要位于台湾。
            </div>
          </div>
          <div style={{ padding: 12, background: "rgba(249,115,22,0.05)", borderRadius: 8, border: "1px solid rgba(249,115,22,0.15)" }}>
            <div style={{ fontWeight: 600, fontSize: 13, color: "#f97316", marginBottom: 4 }}>韩国市场集中风险</div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6 }}>
              EWY极度集中于SK海力士({EWY_SK_HYNIX_WEIGHT}%)和三星(24%)。若HBM降价、AI资本开支下降或存储周期反转，EWY将受较大影响。历史3年Beta约1.63。
            </div>
          </div>
          <div style={{ padding: 12, background: "rgba(168,85,247,0.05)", borderRadius: 8, border: "1px solid rgba(168,85,247,0.15)" }}>
            <div style={{ fontWeight: 600, fontSize: 13, color: "#a855f7", marginBottom: 4 }}>AI周期风险</div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6 }}>
              TSMC、三星、SK海力士已成为亚洲指数主导力量。若AI投资放缓，三者可能同步调整，组合缺乏分散化。
            </div>
          </div>
          <div style={{ padding: 12, background: "rgba(59,130,246,0.05)", borderRadius: 8, border: "1px solid rgba(59,130,246,0.15)" }}>
            <div style={{ fontWeight: 600, fontSize: 13, color: "#3b82f6", marginBottom: 4 }}>韩国市场波动</div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6 }}>
              EWY历史波动远高于标普500，Beta约1.63。市场上涨时涨得更快，下跌时通常也跌得更快。适合风险承受能力较强的投资者。
            </div>
          </div>
        </div>
      </div>

      {/* 交易渠道 */}
      <div className="card">
        <h3>加拿大与香港购买渠道</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 8 }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>加拿大</div>
            <ul style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 2, margin: 0, paddingLeft: 16 }}>
              <li>Interactive Brokers Canada</li>
              <li>Questrade</li>
              <li>Wealthsimple</li>
            </ul>
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>香港</div>
            <ul style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 2, margin: 0, paddingLeft: 16 }}>
              <li>Interactive Brokers Hong Kong</li>
              <li>富途证券</li>
              <li>老虎证券 / 长桥证券</li>
            </ul>
          </div>
        </div>
        <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 8 }}>
          TSM 和 EWY 在上述平台均可直接交易。SK海力士（韩国KOSPI: 000660）需开通韩国交易所权限。
        </div>
      </div>
    </div>
  );
}

export default InvestmentPlan;
