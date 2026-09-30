#!/usr/bin/env bash
# 비동기 리소스 상태 폴링 (원본 check_instance_status / cb_step_poll_* 패턴)

# poll_until_status RESOURCE_ID EXPECTED [TIMEOUT_SEC] [INTERVAL_SEC]
# GET $BASE_URL/api/v1/instances/:id 에서 .status 확인
# BUILD → ACTIVE 또는 ERROR / timeout 처리
poll_until_status() {
  local resource_id="$1"
  local expected="$2"
  local max_sec="${3:-${TIMEOUT_VM_ACTIVE:-300}}"
  local interval="${4:-${POLL_INTERVAL:-5}}"
  local elapsed=0
  local status=""
  local url="${BASE_URL}/api/v1/instances/${resource_id}"

  echo "  poll: target=$expected timeout=${max_sec}s interval=${interval}s id=$resource_id"

  while (( elapsed <= max_sec )); do
    apply_auth_headers
    export LAST_ENDPOINT="GET $url"
    local body
    if ! body=$(http_safe "get-instance" GET "$url"); then
      log_fail "poll" "GET failed http=${HTTP_STATUS:-?} id=$resource_id"
      return 1
    fi

    status=$(safe_jq '.status // .data.status // empty' "$body")
    export RESOURCE_STATUS="$status"
    local remain=$((max_sec - elapsed))
    echo "  ... status=${status:-?} elapsed=${elapsed}s remain=${remain}s"

    if [[ "$status" == "ERROR" ]]; then
      log_fail "poll" "reached ERROR id=$resource_id body_snip=$(printf '%s' "$body" | head -c 200)"
      return 1
    fi
    if [[ "$status" == "$expected" ]]; then
      echo "  poll reached: $expected (${elapsed}s)"
      return 0
    fi

    sleep "$interval"
    elapsed=$((elapsed + interval))
  done

  log_fail "poll" "timeout last_status=${status:-TIMEOUT} expected=$expected id=$resource_id"
  return 1
}
