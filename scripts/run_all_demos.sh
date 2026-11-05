#!/usr/bin/env bash
# stub 기동 → 4개 데모 순차 실행 → stub 종료
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export BASE_URL="${BASE_URL:-http://127.0.0.1:8765}"
export JWT_SECRET="${JWT_SECRET:-demo-only-secret-not-for-prod}"
export DEMO_USERNAME="${DEMO_USERNAME:-qa-demo}"
export DEMO_PASSWORD="${DEMO_PASSWORD:-demo-pass-1234}"
export ACCESS_TOKEN_TTL="${ACCESS_TOKEN_TTL:-8}"

mkdir -p artifacts
STUB_LOG="${ROOT}/artifacts/stub.log"
python3 stub/server.py --host 127.0.0.1 --port 8765 >"$STUB_LOG" 2>&1 &
STUB_PID=$!
cleanup() { kill "$STUB_PID" 2>/dev/null || true; wait "$STUB_PID" 2>/dev/null || true; }
trap cleanup EXIT

for _ in $(seq 1 50); do
  if curl -sf "$BASE_URL/health" >/dev/null; then
    break
  fi
  sleep 0.1
done
curl -sf "$BASE_URL/health" >/dev/null

python3 - <<'PY'
import json, urllib.request
req = urllib.request.Request(
    "http://127.0.0.1:8765/admin/reset",
    data=json.dumps({}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
urllib.request.urlopen(req, timeout=5).read()
PY

echo "== 01 token refresh daemon =="
python3 demos/01_token_refresh/refresh_daemon.py --max-refreshes 2 --skew-seconds 3 --poll-seconds 0.5

echo "== 03 env query =="
python3 demos/03_env_query/query_env.py --tag smoke --prefer-ready

echo "== 02 bulk delete (prefix) =="
python3 demos/02_bulk_delete/bulk_delete.py --prefix qa-smoke-

echo "== 04 csv/xlsx fill =="
python3 demos/04_csv_xlsx/fill_report.py

echo "OK: artifacts under $ROOT/artifacts"
