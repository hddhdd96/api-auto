#!/usr/bin/env bash
# 진입점 (원본 run.sh 메뉴 대신 대표 시나리오 직접 실행)

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f "$ROOT/.env" ]]; then
  echo ".env 파일이 없습니다. 먼저: cp .env.example .env"
  exit 2
fi

if ! command -v curl >/dev/null; then
  echo "curl 이 필요합니다." >&2
  exit 1
fi
if ! command -v jq >/dev/null; then
  echo "jq 가 필요합니다." >&2
  exit 1
fi
if ! command -v envsubst >/dev/null; then
  echo "envsubst (gettext) 가 필요합니다. 또는 data/create_instance.json 을 직접 수정하세요." >&2
  exit 1
fi

chmod +x "$ROOT/scenarios/compute/create_and_delete_instance.sh"
exec bash "$ROOT/scenarios/compute/create_and_delete_instance.sh"
