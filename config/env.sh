#!/usr/bin/env bash
# .env 로드 (실비밀값은 커밋하지 않음)

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${CURL_PATH:=curl}"
: "${JQ_PATH:=jq}"
: "${POLL_INTERVAL:=5}"
: "${TIMEOUT_VM_ACTIVE:=300}"
: "${TIMEOUT_DELETE:=120}"
: "${CONNECT_TIMEOUT:=10}"
: "${MAX_TIME:=60}"
: "${INSTANCE_NAME:=qa-test-instance}"
: "${NETWORK_NAME:=qa-test-network}"

export CURL_PATH JQ_PATH POLL_INTERVAL TIMEOUT_VM_ACTIVE TIMEOUT_DELETE
export CONNECT_TIMEOUT MAX_TIME INSTANCE_NAME NETWORK_NAME
export BASE_URL="${BASE_URL:-}"
export API_TOKEN="${API_TOKEN:-}"
