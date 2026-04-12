#!/usr/bin/env bash
# TenderScout ZA — start backend + frontend

# Run this script
'''
chmod +x start.sh
'''


set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo ""
echo "══════════════════════════════════════════"
echo "  TenderScout ZA — Starting up"
echo "══════════════════════════════════════════"

# ── Backend ────────────────────────────────────
echo ""
echo "▶ Starting backend on http://localhost:8000"

cd "$BACKEND"

# Activate venv (Windows Git Bash + Mac/Linux)
if [ -f "venv/Scripts/activate" ]; then
  source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
else
  echo "✗ No venv found in backend/ — run: python -m venv venv && pip install -r requirements.txt"
  exit 1
fi

# Install/sync deps silently
pip install -r requirements.txt -q

# Start uvicorn in background
python -m uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo "  Waiting for backend..."
for i in {1..20}; do
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "  ✓ Backend ready"
    break
  fi
  sleep 1
done

# ── Frontend ───────────────────────────────────
echo ""
echo "▶ Starting frontend on http://localhost:5173"

cd "$FRONTEND"
npm install -q
npm run dev &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

# ── Summary ────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo "  ✓ TenderScout ZA is running"
echo ""
echo "  Frontend  →  http://localhost:5173"
echo "  Backend   →  http://localhost:8000"
echo "  API docs  →  http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop everything"
echo "══════════════════════════════════════════"
echo ""

# Trap Ctrl+C — kill both processes cleanly
trap "echo ''; echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT
wait
