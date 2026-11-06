#!/usr/bin/env bash
# 로컬 stub API 기동
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export STUB_HOST="${STUB_HOST:-127.0.0.1}"
export STUB_PORT="${STUB_PORT:-8765}"
export JWT_SECRET="${JWT_SECRET:-demo-only-secret-not-for-prod}"
export ACCESS_TOKEN_TTL="${ACCESS_TOKEN_TTL:-8}"
exec python3 stub/server.py --host "$STUB_HOST" --port "$STUB_PORT"
