#!/bin/bash

# AIPMS 启动脚本

echo "=========================================="
echo "AIPMS - 智能酒店管理系统"
echo "=========================================="

# 检查 uv
if ! command -v uv &> /dev/null; then
    echo "未找到 uv，正在安装..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "错误: 未找到 Node.js"
    exit 1
fi

# 启动后端
echo ""
echo ">>> 启动后端服务..."
cd backend

# 使用 uv 同步依赖
echo "安装后端依赖..."
uv sync

# 初始化数据（如果数据库不存在）
if [ ! -f "pms.db" ]; then
    echo "初始化数据库..."
    uv run python init_data.py
fi

# 启动后端（后台运行）
echo "启动 FastAPI 服务 (端口 8000)..."
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

cd ..

# 启动前端
echo ""
echo ">>> 启动前端服务..."
cd frontend

# 安装依赖（如果需要）
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi

# 启动前端
echo "启动 Vite 开发服务器 (端口 3000)..."
npm run dev &
FRONTEND_PID=$!

cd ..

echo ""
echo "=========================================="
echo "系统启动完成！"
echo ""
echo "前端地址: http://localhost:3000"
echo "后端地址: http://localhost:8000"
echo "API文档: http://localhost:8000/docs"
echo ""
echo "默认账号: manager / 123456"
echo "=========================================="
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待并捕获退出信号
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
