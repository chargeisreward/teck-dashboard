#!/bin/bash
# 逐批调用 Wind CLI 获取财务数据，每只超时 15 秒
# 结果保存到 /tmp/wind_financials.jsonl

WIND_SKILL_DIR="$HOME/.claude/skills/wind-mcp-skill"
OUTPUT="/tmp/wind_financials.jsonl"
> "$OUTPUT"  # 清空

declare -A WINDCODES
WINDCODES["NVDA"]="NVDA.O"; WINDCODES["AMD"]="AMD.O"; WINDCODES["INTC"]="INTC.O"
WINDCODES["AVGO"]="AVGO.O"; WINDCODES["QCOM"]="QCOM.O"; WINDCODES["AAPL"]="AAPL.O"
WINDCODES["GOOGL"]="GOOGL.O"; WINDCODES["GFS"]="GFS.O"; WINDCODES["MU"]="MU.O"
WINDCODES["WDC"]="WDC.O"; WINDCODES["ASX"]="ASX.O"; WINDCODES["AMAT"]="AMAT.O"
WINDCODES["LRCX"]="LRCX.O"; WINDCODES["KLAC"]="KLAC.O"; WINDCODES["SNPS"]="SNPS.O"
WINDCODES["CDNS"]="CDNS.O"; WINDCODES["ARM"]="ARM.O"; WINDCODES["AMZN"]="AMZN.O"
WINDCODES["MSFT"]="MSFT.O"; WINDCODES["ORCL"]="ORCL.O"; WINDCODES["META"]="META.O"
WINDCODES["TSLA"]="TSLA.O"; WINDCODES["PDD"]="PDD.O"; WINDCODES["MRVL"]="MRVL.O"
WINDCODES["ANET"]="ANET.O"; WINDCODES["CSCO"]="CSCO.O"; WINDCODES["AMKR"]="AMKR.O"
WINDCODES["TSM"]="TSM.N"; WINDCODES["ASML"]="ASML.N"; WINDCODES["UMC"]="UMC.N"
WINDCODES["TOELY"]="TOELY.O"; WINDCODES["ASMIY"]="ASMIY.O"; WINDCODES["ATEYY"]="ATEYY.O"
WINDCODES["SIEGY"]="SIEGY.O"; WINDCODES["ANSS"]="ANSS.O"
WINDCODES["BIDU"]="09888.HK"; WINDCODES["TCEHY"]="00700.HK"; WINDCODES["BABA"]="09988.HK"
WINDCODES["XIACF"]="01810.HK"; WINDCODES["MPNGY"]="03690.HK"
WINDCODES["SMI"]="688981.SH"

total=${#WINDCODES[@]}
count=0

for ticker in "${!WINDCODES[@]}"; do
    wc="${WINDCODES[$ticker]}"
    question="${wc}202320242025annualrevenuenetincomepe"
    ((count++))
    echo "[$count/$total] $ticker ($wc)..." >&2

    result=$(cd "$WIND_SKILL_DIR" && timeout 15 node scripts/cli.mjs call global_stock_data get_global_stock_fundamentals "{\"question\":\"$question\"}" 2>/dev/null)
    rc=$?

    if [ $rc -eq 0 ] && [ -n "$result" ]; then
        result_one=$(echo "$result" | tr -d '\n\r')
        echo "{\"ticker\":\"$ticker\",\"windcode\":\"$wc\",\"ok\":true,\"data\":$result_one}" >> "$OUTPUT"
        echo "  ✅" >&2
    else
        echo "{\"ticker\":\"$ticker\",\"windcode\":\"$wc\",\"ok\":false}" >> "$OUTPUT"
        echo "  ⏭️ (rc=$rc)" >&2
    fi
done

echo "{\"total\":$total,\"done\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" >> "$OUTPUT"
echo "Done. Results in $OUTPUT" >&2
