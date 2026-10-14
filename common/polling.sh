#!/usr/bin/env bash
# Poll observations; never repeat a failed HTTP request.
poll_until_status() {
  local resource_id="$1" expected="$2" max_sec="${3:-${TIMEOUT_VM_ACTIVE:-300}}"
  local interval="${4:-${POLL_INTERVAL:-5}}" deadline=$((SECONDS + max_sec))
  local url="${BASE_URL}/api/v1/instances/${resource_id}" status
  while :; do
    apply_auth_headers
    export LAST_ENDPOINT="GET $url"
    http_safe get-instance GET "$url" >/dev/null || return 1
    assert_business_success "$HTTP_BODY" || return 1
    status=$(safe_jq '.status // .data.status // empty' "$HTTP_BODY") || return 1
    export RESOURCE_STATUS="$status"
    if [[ "$status" == "$expected" ]]; then return 0; fi
    if [[ "$status" != BUILD && "$status" != CREATING ]]; then
      log_fail poll "예상하지 않은 상태: actual=${status:-empty} expected=$expected id=$resource_id"
      return 1
    fi
    if ((SECONDS >= deadline)); then
      log_fail poll "제한 시간 초과: actual=$status expected=$expected id=$resource_id"
      return 1
    fi
    local remaining=$((deadline - SECONDS))
    ((interval <= remaining)) || interval=$remaining
    sleep "$interval"
  done
}
