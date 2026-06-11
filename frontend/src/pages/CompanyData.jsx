import { useState, useEffect, useCallback } from "react";
import { getCompanyDataBrowse } from "../api";

function CompanyData() {
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [expandedId, setExpandedId] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getCompanyDataBrowse();
      setCompanies(data || []);
    } catch (e) {
      console.error("Failed to fetch company data:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filtered = companies.filter((c) => {
    const term = searchTerm.toLowerCase();
    return (
      !term ||
      (c.name && c.name.toLowerCase().includes(term)) ||
      (c.name_cn && c.name_cn.toLowerCase().includes(term)) ||
      (c.ticker && c.ticker.toLowerCase().includes(term))
    );
  });

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "var(--text, #f1f5f9)" }}>
            数据浏览 · 公司
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--text-secondary, #94a3b8)" }}>
            {companies.length > 0 ? `共 ${companies.length} 家公司 · 含实时行情和财务数据` : "加载中..."}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="搜索公司名/ticker..."
            style={{
              padding: "6px 12px", borderRadius: 6, border: "1px solid var(--border, #334155)",
              background: "var(--card-bg, #1e293b)", color: "var(--text, #f1f5f9)",
              fontSize: 13, width: 200, outline: "none",
            }}
          />
          <button onClick={fetchData} disabled={loading}
            style={{ padding: "6px 16px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--card-bg)", color: "var(--text)", fontSize: 13, cursor: loading ? "wait" : "pointer" }}>
            {loading ? "加载中..." : "刷新"}
          </button>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 60, color: "var(--text-secondary)" }}>加载中...</div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: 40, color: "var(--text-secondary)" }}>
          {searchTerm ? "无匹配结果" : "暂无公司数据"}
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border, #334155)" }}>
                <th style={thStyle}>公司</th>
                <th style={thStyle}>Ticker</th>
                <th style={{ ...thStyle, textAlign: "right" }}>股价</th>
                <th style={{ ...thStyle, textAlign: "right" }}>涨跌幅</th>
                <th style={{ ...thStyle, textAlign: "right" }}>市值(亿)</th>
                <th style={{ ...thStyle, textAlign: "right" }}>PE(TTM)</th>
                <th style={{ ...thStyle, textAlign: "right" }}>营收(亿)</th>
                <th style={{ ...thStyle, textAlign: "right" }}>净利润(亿)</th>
                <th style={{ ...thStyle, textAlign: "right" }}>毛利率</th>
                <th style={{ thStyle, textAlign: "center" }}>来源</th>
                <th style={thStyle}>更新时间</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => {
                const latestFin = c.financials?.[0];
                const priceTime = c.price_time
                  ? new Date(c.price_time).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
                  : "-";

                return (
                  <tr key={c.id}
                    onClick={() => setExpandedId(expandedId === c.id ? null : c.id)}
                    style={{
                      borderBottom: "1px solid var(--border, #334155)",
                      cursor: "pointer",
                      background: expandedId === c.id ? "rgba(59,130,246,0.04)" : "transparent",
                    }}>
                    <td style={tdStyle}>
                      <div style={{ fontWeight: 600, color: "var(--text)" }}>{c.name_cn || c.name}</div>
                      {c.company_type && <div style={{ fontSize: 10, color: "var(--text-secondary)" }}>{c.company_type}</div>}
                    </td>
                    <td style={tdStyle}>
                      <span style={{ color: "var(--accent, #3b82f6)", fontWeight: 600 }}>{c.ticker || "-"}</span>
                    </td>
                    <td style={{ ...tdStyle, textAlign: "right", fontWeight: 700 }}>
                      {c.current_price != null ? `$${c.current_price}` : "-"}
                    </td>
                    <td style={{
                      ...tdStyle, textAlign: "right", fontWeight: 600,
                      color: c.change_pct >= 0 ? "var(--success, #22c55e)" : "var(--error, #ef4444)",
                    }}>
                      {c.change_pct != null ? `${c.change_pct >= 0 ? "+" : ""}${c.change_pct}%` : "-"}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "right" }}>
                      {c.market_cap_b != null ? `${c.market_cap_b.toFixed(0)}` : "-"}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "right" }}>
                      {c.pe_ttm != null ? c.pe_ttm.toFixed(1) : "-"}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "right" }}>
                      {latestFin?.revenue != null ? latestFin.revenue.toFixed(0) : "-"}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "right" }}>
                      {latestFin?.net_income != null ? latestFin.net_income.toFixed(0) : "-"}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "right" }}>
                      {latestFin?.gross_margin != null ? `${latestFin.gross_margin.toFixed(1)}%` : "-"}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "center" }}>
                      <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 3, background: c.data_source === "tencent" ? "rgba(34,197,94,0.12)" : "rgba(100,116,139,0.12)", color: c.data_source === "tencent" ? "#22c55e" : "#64748b" }}>
                        {c.data_source || "N/A"}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, fontSize: 11, color: "var(--text-secondary)" }}>
                      {priceTime}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Legend */}
      <div style={{ marginTop: 20, padding: "8px 12px", fontSize: 11, color: "var(--text-secondary)", borderTop: "1px solid var(--border, #334155)", display: "flex", gap: 16, flexWrap: "wrap" }}>
        <span>数据说明:</span>
        <span>实时行情每15分钟刷新</span>
        <span>财务数据来源: Wind API / 年报</span>
        <span>营收/净利润单位为亿美元</span>
        <span>市值单位为亿美元</span>
      </div>
    </div>
  );
}

const thStyle = { padding: "8px 12px", textAlign: "left", color: "var(--text-secondary, #94a3b8)", fontWeight: 600, fontSize: 11, whiteSpace: "nowrap", borderBottom: "2px solid var(--border, #334155)" };
const tdStyle = { padding: "8px 12px", color: "var(--text-secondary, #94a3b8)", fontSize: 12, borderBottom: "1px solid var(--border, #334155)", whiteSpace: "nowrap" };

export default CompanyData;
