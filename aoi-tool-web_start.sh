#!/usr/bin/env bash
# AOI Tool - RPi launcher (mirrors aoi-web_start.bat)
# Starts backend + frontend in a detachable tmux session.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-57842}"
SESSION="aoi"

[ -d "$PROJECT_DIR/backend" ]  || { echo "[FEHLER] backend/ nicht gefunden";  exit 1; }
[ -d "$PROJECT_DIR/frontend" ] || { echo "[FEHLER] frontend/ nicht gefunden"; exit 1; }
[ -x "$PROJECT_DIR/backend/venv/bin/uvicorn" ] || { echo "[FEHLER] venv fehlt — siehe Setup (python3 -m venv venv)"; exit 1; }

# fresh session
tmux kill-session -t "$SESSION" 2>/dev/null || true

# backend window: load .env overrides, activate venv, run uvicorn
tmux new-session -d -s "$SESSION" -n backend -c "$PROJECT_DIR/backend"
tmux send-keys -t "$SESSION":backend \
  "set -a; [ -f .env ] && . ./.env; set +a; source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port ${BACKEND_PORT} --reload" C-m

# frontend window: vite dev (binds 0.0.0.0:3000 per package.json)
tmux new-window -t "$SESSION" -n frontend -c "$PROJECT_DIR/frontend"
tmux send-keys -t "$SESSION":frontend "npm run dev" C-m

IP="$(hostname -I | awk '{print $1}')"
echo
echo "  ✓ AOI Tool gestartet (tmux-Session '${SESSION}')"
echo "  UI:        http://${IP}:3000"
echo "  Anhängen:  tmux attach -t ${SESSION}"
echo "             (Fenster wechseln: Ctrl-b dann 0/1 · Loslösen: Ctrl-b dann d)"
echo "  Stoppen:   tmux kill-session -t ${SESSION}"
echo
