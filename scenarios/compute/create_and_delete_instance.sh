#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for library in config/env common/logger common/request common/assertion common/polling common/cleanup; do
  source "$ROOT/$library.sh"
done

require_env() {
  [[ -n "$BASE_URL" && -n "$API_TOKEN" ]] || { echo 'BASE_URL/API_TOKEN이 필요합니다.' >&2; return 2; }
  local setting
  for setting in POLL_INTERVAL TIMEOUT_VM_ACTIVE TIMEOUT_DELETE CONNECT_TIMEOUT MAX_TIME; do
    [[ "${!setting}" =~ ^[1-9][0-9]*$ ]] || { echo "$setting: 양의 정수가 필요합니다." >&2; return 2; }
  done
}

create_instance() {
  local payload
  payload=$("$JQ_PATH" --arg name "$INSTANCE_NAME" --arg network "$NETWORK_NAME" '.name=$name | .network=$network' "$ROOT/data/create_instance.json") || return 1
  apply_auth_headers
  export LAST_ENDPOINT="POST ${BASE_URL}/api/v1/instances"
  local request_status=0
  http_request POST "${BASE_URL}/api/v1/instances" "$payload" || request_status=$?
  # A returned ID must remain recoverable even when later assertions fail.
  RESOURCE_ID=$(safe_jq '.id // .data.id // .data.server.id // empty' "$HTTP_BODY") || return 1
  if [[ -n "$RESOURCE_ID" ]]; then
    [[ "$RESOURCE_ID" =~ ^[a-zA-Z0-9_-]+$ ]] || { log_fail create '안전하지 않은 ID 형식'; return 1; }
    track_resource "$RESOURCE_ID" || return 1
  fi
  ((request_status == 0)) || { log_fail create "요청 실패: http=$HTTP_STATUS curl=$HTTP_CURL_EXIT"; return 1; }
  [[ "$HTTP_STATUS" == 200 || "$HTTP_STATUS" == 201 ]] || { log_fail create "예상하지 않은 HTTP: $HTTP_STATUS"; return 1; }
  assert_business_success "$HTTP_BODY" || return 1
  [[ -n "$RESOURCE_ID" ]] || { log_fail create '응답에 ID가 없습니다. 요청한 이름으로 수동 확인이 필요합니다.'; return 1; }
  export RESOURCE_ID
}

validate_instance() {
  apply_auth_headers
  export LAST_ENDPOINT="GET ${BASE_URL}/api/v1/instances/${RESOURCE_ID}"
  http_safe get-instance GET "${BASE_URL}/api/v1/instances/${RESOURCE_ID}" >/dev/null || return 1
  assert_http_status 200 get_http || return 1
  assert_business_success "$HTTP_BODY" || return 1
  assert_jq_equals '.id // .data.id' "$RESOURCE_ID" "$HTTP_BODY" resource_id || return 1
  assert_jq_equals '.name // .data.name' "$INSTANCE_NAME" "$HTTP_BODY" resource_name || return 1
  assert_jq_equals '.status // .data.status' ACTIVE "$HTTP_BODY" status_active
}

main() {
  require_env || return $?
  init_logging "${LOG_DIR:-$ROOT/logs}"
  RESOURCE_RECORD_FILE="${LOG_FILE}.resources.json"
  export RESOURCE_RECORD_FILE
  persist_resources
  install_cleanup_trap
  log_info "scenario=create_and_delete_instance name=$INSTANCE_NAME"
  try_step 'Create Instance' create_instance || return 1
  try_step 'Poll until ACTIVE' poll_until_status "$RESOURCE_ID" ACTIVE || return 1
  try_step 'Validate Instance' validate_instance || return 1
  try_step 'Delete Instance & Verify' delete_instance "$RESOURCE_ID" || return 1
}
main "$@"
