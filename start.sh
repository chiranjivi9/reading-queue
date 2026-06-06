#!/bin/bash
# start.sh — Start both backend and frontend dev servers with one command.
#
# Usage:  ./start.sh
# Stop:   Ctrl+C  (kills both servers)
#
# Requirements:
#   - Python 3.11 venv at backend/venv/
#   - Node 20+ (uses nvm if available)

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Node version ──────────────────────────────────────────────────────────────
if [ -f "$HOME/.nvm/nvm.sh" ]; then
  # shellcheck disable=SC1090
  source "$HOME/.nvm/nvm.sh"
  nvm use 20 --silent 2>/dev/null || nvm use node --silent
fi

# ── Backend ───────────────────────────────────────────────────────────────────
echo "Starting backend..."

VENV_PYTHON="$ROOT/backend/venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
  echo "ERROR: backend/venv not found. Create it with:"
  echo "  cd backend && python3.11 -m venv venv && pip install -r requirements.txt"
  exit 1
fi

# Export VIRTUAL_ENV so uvicorn's --reload subprocesses inherit the venv's Python.
# Using "python -m uvicorn" (not the uvicorn script directly) ensures sys.executable
# points to the venv Python when worker processes are spawned.
export VIRTUAL_ENV="$ROOT/backend/venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"

cd "$ROOT/backend"
"$VENV_PYTHON" -m uvicorn src.main:app --reload --port 8000 &
BACKEND_PID=$!
cd "$ROOT"

# ── Frontend ──────────────────────────────────────────────────────────────────
echo "Starting frontend..."
cd "$ROOT/frontend"

if [ ! -d "node_modules" ]; then
  echo "node_modules not found — running npm install..."
  npm install
fi

npm run dev &
FRONTEND_PID=$!
cd "$ROOT"

# ── Ready ─────────────────────────────────────────────────────────────────────
echo ""
echo "  Backend  →  http://localhost:8000"
echo "  Frontend →  http://localhost:5173"
echo "  API docs →  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

# Shut down both processes cleanly on Ctrl+C
trap 'echo ""; echo "Stopping..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0' INT TERM
wait
