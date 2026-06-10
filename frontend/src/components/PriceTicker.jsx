import { useState, useEffect } from "react";
import { getStockInfo, getPriceHistory } from "../api";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

function PriceTicker({ ticker, nameCn, compact = false }) {
  const [info, setInfo] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!ticker) {
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all([
      getStockInfo(ticker).catch(() => null),
      getPriceHistory(ticker, 30).catch(() => ({ data: [] })),
    ]).then(([infoRes, histRes]) => {
      setInfo(infoRes);
      setHistory(histRes?.data || []);
      setLoading(false);
    });
  }, [ticker]);

  if (!ticker) return null;
  if (loading) {
    return (
      <div className="price-ticker" style={{ padding: "8px 12px", background: "rgba(255,255,255,0.03)", borderRadius: 8, minWidth: 140 }}>
        <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>{nameCn || ticker}</div>
        <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>加载中...</div>
      </div>
    );
  }

  const price = info?.current_price || history?.[history.length - 1]?.price;
  const changePct = info?.change_pct || history?.[history.length - 1]?.change_pct;
  const isUp = changePct != null && changePct >= 0;
  const mcap = info?.market_cap_b;
  const pe = info?.pe_ttm;

  const chartData = history.slice(-20);

  return (
    <div
      className="price-ticker"
      style={{
        padding: "10px 14px",
        background: "rgba(255,255,255,0.03)",
        borderRadius: 8,
        border: "1px solid rgba(255,255,255,0.06)",
        cursor: compact ? "pointer" : "default",
        minWidth: compact ? 120 : 180,
      }}
      onClick={() => compact && setExpanded(!expanded)}
    >
      {/* 名称 */}
      <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 2 }}>
        {nameCn || ticker}
        {!compact && ticker && (
          <span style={{ marginLeft: 4, opacity: 0.5 }}>{ticker}</span>
        )}
      </div>

      {/* 价格 & 涨跌幅 */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontSize: compact ? 15 : 18, fontWeight: 700, color: "#fff" }}>
          {price != null ? `$${price}` : "-"}
        </span>
        {changePct != null && (
          <span style={{
            fontSize: compact ? 11 : 13,
            fontWeight: 600,
            color: isUp ? "var(--accent-green)" : "var(--accent-red)",
          }}>
            {isUp ? "+" : ""}{changePct}%
          </span>
        )}
      </div>

      {/* 估值指标 */}
      {!compact && (
        <div style={{ display: "flex", gap: 12, marginTop: 4, fontSize: 11, color: "var(--text-secondary)" }}>
          {mcap != null && <span>市值: ${mcap}B</span>}
          {pe != null && <span>PE(TTM): {pe}</span>}
        </div>
      )}

      {/* 迷你走势图 */}
      {!compact && chartData.length > 1 && (
        <div style={{ marginTop: 6, height: 40 }}>
          <ResponsiveContainer width="100%" height={40}>
            <LineChart data={chartData}>
              <Line
                type="monotone"
                dataKey="price"
                stroke={isUp ? "var(--accent-green)" : "var(--accent-red)"}
                strokeWidth={1.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* 展开模式 (compact 时) */}
      {compact && expanded && chartData.length > 1 && (
        <div style={{ marginTop: 8, height: 60 }}>
          <ResponsiveContainer width="100%" height={60}>
            <LineChart data={chartData}>
              <Line
                type="monotone"
                dataKey="price"
                stroke={isUp ? "var(--accent-green)" : "var(--accent-red)"}
                strokeWidth={1.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

export default PriceTicker;
