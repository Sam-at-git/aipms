# DevContainer Configuration

This directory contains the development container configuration for AIPMS.

## Features

- **Base Image**: `mcr.microsoft.com/devcontainers/universal:latest`
  - Includes Python 3.11, Node.js LTS, and common development tools
- **Extensions**: Python, ESLint, Prettier, TailwindCSS, Docker, GitLens
- **Port Forwarding**: 3000 (frontend), 8000 (backend)

## Setup

The container will automatically:
1. Install `uv` (Python package manager)
2. Install backend dependencies with `uv sync`
3. Initialize the database with seed data
4. Install frontend dependencies with `npm install`

## Manual Setup

If you need to manually rebuild:

```bash
# Rebuild the container
Ctrl+Shift+P -> "Dev Containers: Rebuild Container"

# Or run post-create script manually
bash .devcontainer/post-create.sh
```

## Quick Start

```bash
# Start both backend and frontend
./start.sh

# Or start individually
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

## Troubleshooting

**uv command not found**:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
```

**Database not initialized**:
```bash
cd backend
uv run python init_data.py
```
