#!/bin/bash
# Zeabur 启动入口：首次运行时从 seed 复制数据库到持久卷
# DB_PATH 由 Zeabur 环境变量或 Dockerfile 默认指定

set -e

DB_PATH="${DB_PATH:-/data/teck_dashboard.db}"
SEED_FILE="/app/seed_db/teck_dashboard.seed"

# 确保数据目录存在
mkdir -p "$(dirname "$DB_PATH")"

# 如果目标 DB 不存在，从 seed 复制
if [ ! -f "$DB_PATH" ]; then
    if [ -f "$SEED_FILE" ]; then
        echo "首次启动：从 seed 复制数据库到 $DB_PATH"
        cp "$SEED_FILE" "$DB_PATH"
        echo "完成：$(ls -lh "$DB_PATH" | awk '{print $5}')"
    else
        echo "警告：seed 数据库不存在，将创建空数据库"
    fi
else
    echo "数据库已存在：$DB_PATH ($(ls -lh "$DB_PATH" | awk '{print $5}'))"
fi

# 启动应用
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8080}"
