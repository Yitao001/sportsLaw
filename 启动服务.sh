#!/bin/bash
# ============================================================
# SportsLax 全服务启动脚本（FastAPI + WebDAV）
# 用法：bash 启动服务.sh
# ============================================================
cd "$(dirname "$0")"
export USERNAME=developer
export USER=developer

echo "============================================"
echo "  SportsLax — 体育法律咨询智能体"
echo "  启动全服务：FastAPI + WebDAV"
echo "============================================"

# 创建必要目录
mkdir -p logs data/chroma_db

# 启动 WebDAV（后台）
echo "[1/2] 启动 WebDAV 知识库挂载服务 (端口 8081)..."
python webdav_server.py &
WEBDAV_PID=$!
echo "       PID: $WEBDAV_PID"

# 等待一秒确保 WebDAV 启动完成
sleep 1

# 启动 FastAPI（前台，保持脚本存活）
echo "[2/2] 启动 FastAPI API 服务 (端口 8000)..."
echo "       Swagger 文档: http://localhost:8000/docs"
echo "       WebDAV 挂载:  http://localhost:8081/"
echo "============================================"
python -m uvicorn api:app --host 0.0.0.0 --port 8000

# FastAPI 退出后，清理 WebDAV
echo ""
echo "FastAPI 已停止，正在关闭 WebDAV..."
kill $WEBDAV_PID 2>/dev/null
echo "所有服务已停止。"
