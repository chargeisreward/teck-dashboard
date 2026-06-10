import { useState, useEffect } from "react";
import { getHotStocks } from "../api";

function HotStocksPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getHotStocks()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="card">
        <h3>A股热点榜</h3>
        <div style={{ color: "var(--text-secondary)", fontSize: 13 }}>加载中...</div>
      </div>
    );
  }

  if (!data || (!data.gainers?.length && !data.losers?.length)) {
    return null;
  }

  return (
    <div className="card">
      <h3>A股热点榜</h3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* 涨幅榜 */}
        <div>
          <div style={{ fontSize: 12, color: "var(--accent-green)", fontWeight: 600, marginBottom: 8 }}>
            ↑ 涨幅榜
          </div>
          <table style={{ width: "100%", fontSize: 12 }}>
            <thead>
              <tr style={{ color: "var(--text-secondary)" }}>
                <th style={{ textAlign: "left" }}>代码</th>
                <th style={{ textAlign: "left" }}>名称</th>
                <th style={{ textAlign: "right" }}>最新价</th>
                <th style={{ textAlign: "right" }}>涨幅</th>
              </tr>
            </thead>
            <tbody>
              {data.gainers.map((g) => (
                <tr key={g.code}>
                  <td style={{ color: "var(--text-secondary)" }}>{g.code}</td>
                  <td>{g.name}</td>
                  <td style={{ textAlign: "right" }}>{g.price}</td>
                  <td style={{ textAlign: "right", color: "var(--accent-green)", fontWeight: 600 }}>
                    +{g.change_pct}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {/* 跌幅榜 */}
        <div>
          <div style={{ fontSize: 12, color: "var(--accent-red)", fontWeight: 600, marginBottom: 8 }}>
            ↓ 跌幅榜
          </div>
          <table style={{ width: "100%", fontSize: 12 }}>
            <thead>
              <tr style={{ color: "var(--text-secondary)" }}>
                <th style={{ textAlign: "left" }}>代码</th>
                <th style={{ textAlign: "left" }}>名称</th>
                <th style={{ textAlign: "right" }}>最新价</th>
                <th style={{ textAlign: "right" }}>跌幅</th>
              </tr>
            </thead>
            <tbody>
              {data.losers.map((g) => (
                <tr key={g.code}>
                  <td style={{ color: "var(--text-secondary)" }}>{g.code}</td>
                  <td>{g.name}</td>
                  <td style={{ textAlign: "right" }}>{g.price}</td>
                  <td style={{ textAlign: "right", color: "var(--accent-red)", fontWeight: 600 }}>
                    {g.change_pct}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 8 }}>
        数据来源: AKShare | A股实时行情
      </div>
    </div>
  );
}

export default HotStocksPanel;
