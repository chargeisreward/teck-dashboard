/**
 * Wind 财务数据 — 直接获取并写入 SQLite
 * 遍历所有 ticker，调用 Wind CLI，结果写入 Financial 表
 * 用法: node wind_fetch_and_save.mjs
 */
import { execSync } from "child_process";
import { join } from "path";
import { homedir } from "os";
import Database from "better-sqlite3"; // 需先 npm install better-sqlite3

const SKILL_DIR = join(homedir(), ".claude", "skills", "wind-mcp-skill");
const CLI = join(SKILL_DIR, "scripts", "cli.mjs");
const DB_PATH = join(process.cwd(), "teck_dashboard.db");

const WINDCODES = {
  NVDA: "NVDA.O", AMD: "AMD.O", INTC: "INTC.O", AVGO: "AVGO.O",
  QCOM: "QCOM.O", AAPL: "AAPL.O", GOOGL: "GOOGL.O", GFS: "GFS.O",
  MU: "MU.O", WDC: "WDC.O", ASX: "ASX.O", AMAT: "AMAT.O",
  LRCX: "LRCX.O", KLAC: "KLAC.O", SNPS: "SNPS.O", CDNS: "CDNS.O",
  ARM: "ARM.O", AMZN: "AMZN.O", MSFT: "MSFT.O", ORCL: "ORCL.O",
  META: "META.O", TSLA: "TSLA.O", PDD: "PDD.O", MRVL: "MRVL.O",
  ANET: "ANET.O", CSCO: "CSCO.O", AMKR: "AMKR.O",
  TSM: "TSM.N", ASML: "ASML.N", UMC: "UMC.N",
  TOELY: "TOELY.O", ASMIY: "ASMIY.O", ATEYY: "ATEYY.O",
  SIEGY: "SIEGY.O", ANSS: "ANSS.O",
  BIDU: "09888.HK", TCEHY: "00700.HK", BABA: "09988.HK",
  XIACF: "01810.HK", MPNGY: "03690.HK",
  SMI: "688981.SH",
};

function windCall(windcode) {
  const question = `${windcode}202320242025annualrevenuenetincomepe`;
  const cmd = `node "${CLI}" call global_stock_data get_global_stock_fundamentals '${JSON.stringify({ question })}'`;
  try {
    const out = execSync(cmd, { cwd: SKILL_DIR, timeout: 20000, encoding: "utf-8", stdio: ["pipe", "pipe", "pipe"] });
    const parsed = JSON.parse(out);
    const text = parsed?.content?.[0]?.text;
    if (!text) return null;
    const payload = JSON.parse(text);
    return payload?.data?.data?.rows || null;
  } catch {
    return null;
  }
}

function parseRows(rows, columns) {
  const colNames = columns.map(c => c.name);
  const revIdx = colNames.findIndex(n => n.includes("营业收入") && !n.includes("时间"));
  const netIdx = colNames.findIndex(n => n.includes("净利润") && !n.includes("时间"));
  const peIdx = colNames.findIndex(n => n.includes("市盈率") && !n.includes("时间"));
  const timeIdx = colNames.findIndex(n => n.includes("时间"));
  if (revIdx < 0 || timeIdx < 0) return [];

  return rows.map(row => {
    const ts = row[timeIdx];
    if (!ts || !ts.includes("FY")) return null;
    const fy = parseInt(ts.split("FY")[1]);
    if (!fy) return null;
    return {
      fiscal_year: fy,
      revenue: row[revIdx] != null ? Math.round(row[revIdx] * 0.1 * 100) / 100 : null,
      net_income: row[netIdx] != null ? Math.round(row[netIdx] * 0.1 * 100) / 100 : null,
      pe: row[peIdx] != null ? Math.round(row[peIdx] * 100) / 100 : null,
    };
  }).filter(Boolean);
}

// --- main ---
console.error(`DB: ${DB_PATH}`);
console.error(`Skill: ${SKILL_DIR}`);

const db = new Database(DB_PATH);
const entries = Object.entries(WINDCODES);

// 获取公司 map
const companies = db.prepare("SELECT id, ticker FROM companies WHERE ticker IS NOT NULL").all();
const tickerToIds = {};
for (const c of companies) {
  const t = c.ticker.toUpperCase().trim();
  (tickerToIds[t] ??= []).push(c.id);
}

let updated = 0, skipped = 0;

for (const [ticker, windcode] of entries) {
  const ids = tickerToIds[ticker];
  if (!ids) { console.error(`[${ticker}] No company in DB`); skipped++; continue; }

  const rows = windCall(windcode);
  if (!rows || !rows.length) { console.error(`[${ticker}] ⏭️ no data`); skipped++; continue; }

  // rows[0] = header row with column names when coming from fundamentals NL tool
  // Check if first element is array (actual data) or object (column info)
  let dataRows, columns;
  if (Array.isArray(rows)) {
    // rows is [columns_array, ...data_rows] or just [data_rows]
    // Check the structure
    if (rows.length >= 2 && rows[0]?.columns) {
      columns = rows[0].columns;
      dataRows = rows.slice(1);
    } else if (rows.length >= 2 && rows[1]?.columns) {
      columns = rows[1].columns;
      dataRows = rows.slice(2);
    } else if (rows[0]?.columns) {
      columns = rows[0].columns;
      dataRows = rows.slice(1);
    } else {
      // Try the wrapped structure that NL tools return
      const data = rows;
      if (data?.[0]?.data?.columns) {
        columns = data[0].data.columns;
        dataRows = data[0].data.rows;
      } else {
        console.error(`[${ticker}] Unknown structure: ${JSON.stringify(rows).slice(0,100)}`);
        skipped++; continue;
      }
    }
  }

  if (!columns) {
    console.error(`[${ticker}] No columns found`);
    skipped++; continue;
  }

  const records = parseRows(dataRows, columns);
  if (!records.length) { console.error(`[${ticker}] No records parsed`); skipped++; continue; }

  const upsert = db.prepare(`
    INSERT INTO financials (company_id, fiscal_year, revenue, net_income, pe, pe_ttm)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(company_id, fiscal_year) DO UPDATE SET
      revenue = excluded.revenue,
      net_income = excluded.net_income,
      pe = excluded.pe,
      pe_ttm = excluded.pe_ttm
  `);

  const tx = db.transaction(() => {
    for (const id of ids) {
      for (const rec of records) {
        upsert.run(id, rec.fiscal_year, rec.revenue, rec.net_income, rec.pe, rec.pe);
      }
    }
  });
  tx();
  updated++;
  console.error(`[${ticker}] ✅ ${windcode} -> ${records.map(r => `FY${r.fiscal_year}`).join(", ")}`);
}

console.error(`\nDone: ${updated} updated, ${skipped} skipped`);
db.close();
