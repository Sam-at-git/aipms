#!/bin/bash
set -e

echo "🚀 Setting up AIPMS development environment..."

# Verify tools (already installed in Dockerfile)
echo "🔍 Checking installed tools..."
echo "  Python: $(python --version)"
echo "  Node.js: $(node --version)"
echo "  npm: $(npm --version)"
echo "  uv: $(uv --version)"
echo "  git: $(git --version)"
echo "  User: $(whoami)"

# Setup backend
echo "🐍 Setting up backend..."
cd /workspace/backend
uv sync
echo "✅ Backend dependencies installed"

# Initialize database if not exists
if [ ! -f aipms.db ]; then
    echo "🗄️  Initializing database..."
    uv run python init_data.py
    echo "✅ Database initialized"
fi

# Setup frontend
echo "📦 Setting up frontend..."
cd /workspace/frontend
if [ ! -d node_modules ]; then
    npm install
    echo "✅ Frontend dependencies installed"
else
    echo "✅ Frontend dependencies already installed"
fi

cd /workspace

echo ""
echo "✨ Development environment ready!"
echo ""
echo "📝 Quick start commands:"
echo "  Backend:  cd backend && uv run uvicorn app.main:app --reload --port 8020"
echo "  Frontend: cd frontend && npm run dev"
echo "  Combined: ./start.sh"
echo ""
echo "📍 URLs:"
echo "  Frontend: http://localhost:3020"
echo "  Backend:  http://localhost:8020"
echo "  API Docs: http://localhost:8020/docs"
