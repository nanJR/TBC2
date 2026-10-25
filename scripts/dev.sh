#!/usr/bin/env bash
# Start the back end and front end together, with each log line tagged
# [api] or [web] so you can tell them apart. Ctrl-C stops both.
#
# Usage (from anywhere):  ./scripts/dev.sh
# Other ports, e.g. if another project already uses 8000:
#   API_PORT=8100 WEB_PORT=3100 ./scripts/dev.sh

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"

# Tell each side where the other one is (read by app/config.py and lib/api.ts).
export FRONTEND_ORIGIN="http://localhost:$WEB_PORT"
export NEXT_PUBLIC_API_URL="http://localhost:$API_PORT"

# Refuse to start on a port something else is already using, instead of
# silently talking to the wrong server.
port_busy() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
for port in "$API_PORT" "$WEB_PORT"; do
  if port_busy "$port"; then
    echo "Port $port is already in use (another project?)." >&2
    echo "Try: API_PORT=8100 WEB_PORT=3100 ./scripts/dev.sh" >&2
    exit 1
  fi
done

for tool in uv node npm; do
  if ! command -v "$tool" >/dev/null; then
    echo "Missing '$tool'. See 'Run it locally' in README.md." >&2
    exit 1
  fi
done

# Install front end packages the first time.
if [ ! -d "$ROOT/apps/web/node_modules" ]; then
  echo "[web] installing packages (first run only)..."
  (cd "$ROOT/apps/web" && npm install)
fi

# Stop both servers when this script exits (Ctrl-C, closing the pane, etc.).
# The handler removes itself first, so "kill 0" can't trigger it again.
cleanup() {
  trap - EXIT INT TERM
  kill 0 2>/dev/null
}
trap cleanup EXIT INT TERM

# Colours make the two tags easy to spot: cyan for api, magenta for web.
tag() { sed -u "s/^/$(printf '\033[%sm[%s]\033[0m ' "$1" "$2")/"; }

(cd "$ROOT/services/api" && uv run fastapi dev app/main.py --port "$API_PORT" 2>&1 | tag 36 api) &
(cd "$ROOT/apps/web" && npm run dev -- --port "$WEB_PORT" 2>&1 | tag 35 web) &

# Keep running until one of the servers stops.
wait -n
