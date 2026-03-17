#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_DIR="$ROOT_DIR/web"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
DEFAULT_SOURCE="https://github.com/tinasheosewe/RepoLens.git"
REPO_SOURCE="${1:-$DEFAULT_SOURCE}"

BACKEND_PID=""

kill_port() {
  local port="$1"
  local pids

  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "Clearing port $port"
    kill -9 $pids 2>/dev/null || true
  fi
}

cleanup() {
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Missing virtualenv Python at $VENV_PYTHON"
  echo "Create the environment and install dependencies first."
  exit 1
fi

if [[ ! -f "$WEB_DIR/package.json" ]]; then
  echo "Missing frontend package.json at $WEB_DIR/package.json"
  exit 1
fi

kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"

echo "Starting backend on http://$BACKEND_HOST:$BACKEND_PORT for source: $REPO_SOURCE"
TRACE_REPO_PATH="$REPO_SOURCE" \
TRACE_BACKEND_HOST="$BACKEND_HOST" \
TRACE_BACKEND_PORT="$BACKEND_PORT" \
"$VENV_PYTHON" - <<'PY' &
import os

import uvicorn

from trace_engine.api.server import create_app

repo_path = os.environ["TRACE_REPO_PATH"]
host = os.environ["TRACE_BACKEND_HOST"]
port = int(os.environ["TRACE_BACKEND_PORT"])

uvicorn.run(create_app(repo_path=repo_path), host=host, port=port, log_level="warning")
PY
BACKEND_PID="$!"

echo "Starting frontend on http://$FRONTEND_HOST:$FRONTEND_PORT"
cd "$WEB_DIR"
npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"