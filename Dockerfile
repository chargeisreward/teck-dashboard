# ==========================================
# Stage 1: 构建前端 (Node)
# ==========================================
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ==========================================
# Stage 2: 运行后端 (Python) + 服务前端
# ==========================================
FROM python:3.11-slim
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends gcc libgomp1 && rm -rf /var/lib/apt/lists/*

# 安装后端依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码（含 seed 数据库）
COPY backend/ ./

# 复制前端构建产物
COPY --from=frontend-build /app/frontend/dist ./static

# entrypoint 脚本设为可执行
RUN chmod +x /app/entrypoint.sh

# Zeabur 默认端口 8080
EXPOSE 8080

# 默认数据库路径（Zeabur 可挂载持久卷到 /data）
ENV DB_PATH=/data/teck_dashboard.db

# 启动入口（处理 seed DB 复制后启动 uvicorn）
CMD ["/bin/bash", "/app/entrypoint.sh"]
