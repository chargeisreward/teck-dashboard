#!/bin/bash
# ============================================================
# 备份 Zeabur 端 Follow 数据到环境变量 FOLLOW_BACKUP
# (跨 redeploy 保护: 环境变量持久化, 启动时自动恢复)
# ============================================================
set -e

# Zeabur 服务 ID (项目 untitled / 服务 t / 环境 production)
SERVICE_ID="6a2ab73e4a7ea31c689a1258"
ENV_ID="6a2ab4be05a35017ba906658"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ZEABUR_CLI="$SCRIPT_DIR/../zeabur_cli/zeabur.exe"

if [ ! -f "$ZEABUR_CLI" ]; then
    # 退回到 PATH 搜索
    ZEABUR_CLI="zeabur"
fi

echo "🔍 提取 Follow 数据..."
FOLLOW_JSON=$("$ZEABUR_CLI" service exec \
    --id "$SERVICE_ID" \
    --env-id "$ENV_ID" \
    -- python3 -c "
import sqlite3, json
c = sqlite3.connect('/data/teck_dashboard.db').cursor()
follows = []
for r in c.execute('SELECT f.company_id, f.weight FROM follows f ORDER BY f.created_at'):
    follows.append({'company_id': r[0], 'weight': r[1]})
print(json.dumps(follows, ensure_ascii=False, separators=(',', ':')))
")

if [ -z "$FOLLOW_JSON" ] || [ "$FOLLOW_JSON" = "[]" ]; then
    echo "⚠️  无 Follow 数据, 跳过备份"
    exit 0
fi

echo "📋 Follow data: $FOLLOW_JSON"

B64=$(echo -n "$FOLLOW_JSON" | base64 -w0)
echo "📦 Saved to env var (${#B64} chars)"

# 写入临时 .env 文件并导入
TMP_ENV=$(mktemp)
echo "FOLLOW_BACKUP=${B64}" > "$TMP_ENV"
"$ZEABUR_CLI" variable env \
    --id "$SERVICE_ID" \
    --env-id "$ENV_ID" \
    --file "$TMP_ENV" 2>&1 | head -5
rm -f "$TMP_ENV"

echo ""
echo "✅ Follow 备份完成! 下次 redeploy 后自动恢复。"
echo "   ⚠️  需要手动 restart 让新 env var 生效:"
echo "     zeabur service restart --id $SERVICE_ID --env-id $ENV_ID -y"
