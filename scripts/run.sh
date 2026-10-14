#!/usr/bin/env bash
# 진입점 (원본 run.sh 메뉴 대신 대표 시나리오 직접 실행)

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v curl >/dev/null; then
  echo "curl 이 필요합니다." >&2
  exit 1
fi
if ! command -v jq >/dev/null; then
  echo "jq 가 필요합니다." >&2
  exit 1
fi
exec bash "$ROOT/scenarios/compute/create_and_delete_instance.sh"
