#!/bin/bash
# Wind 财务数据批量获取脚本
# 必须在 Wind skill 目录下运行 CLI
# 使用方式: bash wind_fetch_financials.sh | python ingest_wind_financials.py

WIND_SKILL_DIR="$HOME/.claude/skills/wind-mcp-skill"

declare -A WINDCODES
# US Stocks (NASDAQ .O)
WINDCODES["NVDA"]="NVDA.O"
WINDCODES["AMD"]="AMD.O"
WINDCODES["INTC"]="INTC.O"
WINDCODES["AVGO"]="AVGO.O"
WINDCODES["QCOM"]="QCOM.O"
WINDCODES["AAPL"]="AAPL.O"
WINDCODES["GOOGL"]="GOOGL.O"
WINDCODES["GFS"]="GFS.O"
WINDCODES["MU"]="MU.O"
WINDCODES["WDC"]="WDC.O"
WINDCODES["ASX"]="ASX.O"
WINDCODES["AMAT"]="AMAT.O"
WINDCODES["LRCX"]="LRCX.O"
WINDCODES["KLAC"]="KLAC.O"
WINDCODES["SNPS"]="SNPS.O"
WINDCODES["CDNS"]="CDNS.O"
WINDCODES["ARM"]="ARM.O"
WINDCODES["AMZN"]="AMZN.O"
WINDCODES["MSFT"]="MSFT.O"
WINDCODES["ORCL"]="ORCL.O"
WINDCODES["META"]="META.O"
WINDCODES["TSLA"]="TSLA.O"
WINDCODES["PDD"]="PDD.O"
WINDCODES["MRVL"]="MRVL.O"
WINDCODES["ANET"]="ANET.O"
WINDCODES["CSCO"]="CSCO.O"
WINDCODES["AMKR"]="AMKR.O"
# NYSE .N
WINDCODES["TSM"]="TSM.N"
WINDCODES["ASML"]="ASML.N"
WINDCODES["UMC"]="UMC.N"
# OTC
WINDCODES["TOELY"]="TOELY.O"
WINDCODES["ASMIY"]="ASMIY.O"
WINDCODES["ATEYY"]="ATEYY.O"
WINDCODES["SIEGY"]="SIEGY.O"
WINDCODES["ANSS"]="ANSS.O"
# HK
WINDCODES["BIDU"]="09888.HK"
WINDCODES["TCEHY"]="00700.HK"
WINDCODES["BABA"]="09988.HK"
WINDCODES["XIACF"]="01810.HK"
WINDCODES["MPNGY"]="03690.HK"
# A-share
WINDCODES["SMI"]="688981.SH"

echo "{\"total\": ${#WINDCODES[@]}, \"started\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"

for ticker in "${!WINDCODES[@]}"; do
    wc="${WINDCODES[$ticker]}"
    question="${wc}202320242025annualrevenuenetincomepe"
    result=$(cd "$WIND_SKILL_DIR" && node scripts/cli.mjs call global_stock_data get_global_stock_fundamentals "{\"question\":\"$question\"}" 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$result" ]; then
        # compress multi-line JSON to single line for JSONL output
        result_one=$(echo "$result" | tr -d '\n\r')
        echo "{\"ticker\":\"$ticker\",\"windcode\":\"$wc\",\"ok\":true,\"data\":$result_one}"
    else
        echo "{\"ticker\":\"$ticker\",\"windcode\":\"$wc\",\"ok\":false}"
    fi
done

echo "{\"done\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
