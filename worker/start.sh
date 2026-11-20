#!/usr/bin/env bash
# Starts the Jhalak worker on :8787 and a Cloudflare quick tunnel, then prints the public URL.
set -euo pipefail
cd "$(dirname "$0")"
source .venv/bin/activate
PORT=${PORT:-8787}
uvicorn jhalak.api:app --host 127.0.0.1 --port "$PORT" > worker.log 2>&1 &
WORKER_PID=$!
trap 'kill $WORKER_PID $TUNNEL_PID 2>/dev/null' EXIT
sleep 2
cloudflared tunnel --url "http://127.0.0.1:$PORT" > tunnel.log 2>&1 &
TUNNEL_PID=$!
echo "Waiting for tunnel..."
for i in $(seq 1 30); do
  URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' tunnel.log | head -1 || true)
  [ -n "$URL" ] && break
  sleep 1
done
echo ""
echo "  Worker URL: ${URL:-<not found, see tunnel.log>}"
echo "  Paste it in Studio > Worker status, or set WORKER_URL in Vercel."
echo "  Logs: tail -f worker.log"
echo ""
wait $WORKER_PID
