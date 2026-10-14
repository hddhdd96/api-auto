#!/usr/bin/env bash
CREATED_IDS=()
DELETE_ATTEMPTED_IDS=()

persist_resources() {
  [[ -n "${RESOURCE_RECORD_FILE:-}" ]] || return 0
  printf '%s\n' "${CREATED_IDS[@]:-}" | "${JQ_PATH:-jq}" -Rsc 'split("\n") | map(select(length > 0))' >"$RESOURCE_RECORD_FILE"
}

track_resource() {
  local existing
  for existing in "${CREATED_IDS[@]:-}"; do
    [[ "$existing" != "$1" ]] || return 0
  done
  CREATED_IDS+=("$1")
  persist_resources
}

untrack_resource() {
  local id
  local -a remaining=()
  for id in "${CREATED_IDS[@]:-}"; do
    [[ -z "$id" || "$id" == "$1" ]] || remaining+=("$id")
  done
  CREATED_IDS=("${remaining[@]:-}")
  persist_resources
}

wait_resource_deleted() {
  local resource_id="$1" max_sec="${2:-${TIMEOUT_DELETE:-120}}"
  local interval="${POLL_INTERVAL:-5}" deadline=$((SECONDS + max_sec))
  local url="${BASE_URL}/api/v1/instances/${resource_id}"
  while :; do
    apply_auth_headers
    export LAST_ENDPOINT="GET $url"
    if http_request GET "$url"; then
      : # Accepted request, resource still visible.
    elif ((HTTP_CURL_EXIT == 0)) && [[ "$HTTP_STATUS" == 404 || "$HTTP_STATUS" == 410 ]]; then
      return 0
    else
      log_fail cleanup "삭제 확인 요청 실패: http=$HTTP_STATUS curl=$HTTP_CURL_EXIT id=$resource_id"
      return 1
    fi
    if ((SECONDS >= deadline)); then
      log_fail cleanup "삭제 확인 제한 시간 초과: id=$resource_id"
      return 1
    fi
    local remaining=$((deadline - SECONDS))
    ((interval <= remaining)) || interval=$remaining
    sleep "$interval"
  done
}

delete_instance() {
  local resource_id="$1" attempted
  for attempted in "${DELETE_ATTEMPTED_IDS[@]:-}"; do
    if [[ "$attempted" == "$resource_id" ]]; then
      log_fail cleanup "이미 삭제를 시도한 ID는 자동 재시도하지 않음: $resource_id"
      return 1
    fi
  done
  DELETE_ATTEMPTED_IDS+=("$resource_id")
  apply_auth_headers
  export LAST_ENDPOINT="DELETE ${BASE_URL}/api/v1/instances/${resource_id}"
  if http_request DELETE "${BASE_URL}/api/v1/instances/${resource_id}"; then
    wait_resource_deleted "$resource_id" || return 1
  elif ! { ((HTTP_CURL_EXIT == 0)) && [[ "$HTTP_STATUS" == 404 || "$HTTP_STATUS" == 410 ]]; }; then
    log_fail cleanup "삭제 실패: http=$HTTP_STATUS curl=$HTTP_CURL_EXIT id=$resource_id"
    return 1
  fi
  untrack_resource "$resource_id"
}

cleanup_tracked() {
  local id failed=0
  local -a pending=("${CREATED_IDS[@]:-}")
  for id in "${pending[@]}"; do
    [[ -n "$id" ]] || continue
    delete_instance "$id" || failed=1
  done
  persist_resources
  return "$failed"
}

finish_scenario() {
  local original_status="$1" cleanup_status=0
  trap - EXIT INT TERM
  cleanup_tracked || cleanup_status=$?
  if ((cleanup_status != 0)); then
    log_fail cleanup "잔여 ID를 보존했습니다: $RESOURCE_RECORD_FILE"
  fi
  print_summary || { ((original_status != 0)) || original_status=1; }
  ((original_status != 0 || cleanup_status == 0)) || original_status=1
  exit "$original_status"
}

install_cleanup_trap() {
  trap 'finish_scenario "$?"' EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
}
