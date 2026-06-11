/**
 * Wind 财务数据批量获取脚本 (Node.js)
 * 调用 Wind MCP CLI 获取所有股票的 3 年财务数据，输出 JSONL 到 stdout
 * 用法: node wind_fetch_all.mjs | python ingest_wind_financials.py
 */
import { execSync } from "child_process";
import { join } from "path";
import { homedir } from "os";

const SKILL_DIR = join(homedir(), ".claude", "skills", "wind-mcp-skill");
const CLI = join(SKILL_DIR, "scripts", "cli.mjs");

const WINDCODES = {
  // NASDAQ .O
  NVDA: "NVDA.O", AMD: "AMD.O", INTC: "INTC.O", AVGO: "AVGO.O",
  QCOM: "QCOM.O", AAPL: "AAPL.O", GOOGL: "GOOGL.O", GFS: "GFS.O",
  MU: "MU.O", WDC: "WDC.O", ASX: "ASX.O", AMAT: "AMAT.O",
  LRCX: "LRCX.O", KLAC: "KLAC.O", SNPS: "SNPS.O", CDNS: "CDNS.O",
  ARM: "ARM.O", AMZN: "AMZN.O", MSFT: "MSFT.O", ORCL: "ORCL.O",
  META: "META.O", TSLA: "TSLA.O", PDD: "PDD.O", MRVL: "MRVL.O",
  ANET: "ANET.O", CSCO: "CSCO.O", AMKR: "AMKR.O",
  // NYSE .N
  TSM: "TSM.N", ASML: "ASML.N", UMC: "UMC.N",
  // OTC
  TOELY: "TOELY.O", ASMIY: "ASMIY.O", ATEYY: "ATEYY.O",
  SIEGY: "SIEGY.O", ANSS: "ANSS.O",
  // HK
  BIDU: "09888.HK", TCEHY: "00700.HK", BABA: "09988.HK",
  XIACF: "01810.HK", MPNGY: "03690.HK",
  // A-share
  SMI: "688981.SH",
};

const entries = Object.entries(WINDCODES);
console.error(`Processing ${entries.length} tickers...`);

for (const [ticker, windcode] of entries) {
  const question = `${windcode}202320242025annualrevenuenetincomepe`;
  const params = JSON.stringify({ question });
  const cmd = `cd "${SKILL_DIR}" && node "${CLI}" call global_stock_data get_global_stock_fundamentals '${params}'`;

  try {
    const stdout = execSync(cmd, { timeout: 20000, encoding: "utf-8", stdio: ["pipe", "pipe", "ignore"] });
    // Validate JSON
    const parsed = JSON.parse(stdout);
    if (parsed?.content?.[0]?.text) {
      const result = { ticker, windcode, ok: true, data: parsed };
      console.log(JSON.stringify(result));
      console.error(`[${ticker}] ✅ ${windcode}`);
    } else {
      console.log(JSON.stringify({ ticker, windcode, ok: false }));
      console.error(`[${ticker}] ⏭️ no data`);
    }
  } catch (e) {
    console.log(JSON.stringify({ ticker, windcode, ok: false, error: e.message?.slice(0, 100) }));
    console.error(`[${ticker}] ⏭️ ${e.message?.slice(0, 60)}`);
  }
}

console.error("Done.");
