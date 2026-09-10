#!/usr/bin/env bash

set -euo pipefail

echo "========================================"
echo " ORI Manager - Development Environment"
echo "========================================"

echo ""
echo "[1/3] Checking uv..."

UV_BIN="$HOME/.local/bin/uv"

if [ ! -x "$UV_BIN" ]; then
    echo "uv not found. Installing uv..."
    curl --proto '=https' --tlsv1.2 -LsSf \
        https://releases.astral.sh/github/uv/releases/download/0.12.12/uv-installer.sh \
        | sh
else
    echo "uv already installed."
fi

echo ""
echo "[2/3] Installing backend dependencies..."

cd /workspace/backend
"$UV_BIN" sync --frozen

echo ""
echo "[3/3] Installing frontend dependencies..."

cd /workspace/frontend
npm ci

echo ""
echo "========================================"
echo " ORI Manager environment ready"
echo "========================================"
echo ""
echo "Backend:"
echo "  cd /workspace/backend"
echo "  uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "Frontend:"
echo "  cd /workspace/frontend"
echo "  npm run dev -- --host 0.0.0.0"
