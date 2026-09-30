#!/usr/bin/env bash
# 대표 시나리오: Instance 생성 → HTTP/Body 검증 → ACTIVE 폴링 → 삭제 → 삭제 확인
# 원본 Compute(Nova) create/poll/delete 흐름을 비식별화한 재구성

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/config/env.sh"
# shellcheck source=/dev/null
source "$ROOT/common/logger.sh"
# shellcheck source=/dev/null
source "$ROOT/common/request.sh"
# shellcheck source=/dev/null
source "$ROOT/common/assertion.sh"
# shellcheck source=/dev/null
source "$ROOT/common/polling.sh"
# shellcheck source=/dev/null
source "$ROOT/common/cleanup.sh"

require_env() {
  local missing=0
  local k
  for k in BASE_URL API_TOKEN; do
    if [[ -z "${!k:-}" ]]; then
      echo "필수 환경변수 없음: $k (.env 확인)" >&2
      missing=1
    fi
  done
  ((missing == 0))
}

create_instance() {
  local name="${INSTANCE_NAME:-qa-test-instance}"
  local payload
  payload=$(INSTANCE_NAME="$name" NETWORK_NAME="${NETWORK_NAME:-qa-test-network}" \
    envsubst <"$ROOT/data/create_instance.json")

  local url="${BASE_URL}/api/v1/instances"
  apply_auth_headers
  export LAST_ENDPOINT="POST $url"

  local body
  body=$(http_safe "create-instance" POST "$url" "$payload") || return 1
  # 원본은 HTTP + returnCode를 함께 봄. 포트폴리오 예제는 2xx(200/201)만 명시적으로 허용
  if [[ "${HTTP_STATUS:-}" != "200" && "${HTTP_STATUS:-}" != "201" ]]; then
    log_fail "create_http" "unexpected HTTP ${HTTP_STATUS:-empty}"
    return 1
  fi

  RESOURCE_ID=$(safe_jq '.id // .data.id // .data.server.id // empty' "$body")
  if [[ -z "$RESOURCE_ID" ]]; then
    log_fail "create" "response에 id 없음"
    printf '%s\n' "$body" | head -20 >&2
    return 1
  fi

  track_resource "$RESOURCE_ID"
  export RESOURCE_ID
  echo "  created id=$RESOURCE_ID name=$name http=$HTTP_STATUS time=${HTTP_TIME:-?}s"
}

validate_instance() {
  local url="${BASE_URL}/api/v1/instances/${RESOURCE_ID}"
  apply_auth_headers
  export LAST_ENDPOINT="GET $url"
  local body
  body=$(http_safe "get-instance" GET "$url") || return 1
  assert_http_status "200" "get_http" || return 1
  assert_jq_equals '.status // .data.status' "ACTIVE" "$body" "status_active" || return 1
  local name
  name=$(safe_jq '.name // .data.name // empty' "$body")
  echo "  validated id=$RESOURCE_ID name=${name:-?} status=ACTIVE"
}

delete_and_verify() {
  delete_instance "$RESOURCE_ID" || return 1
  # track 목록에서 제거 (중복 cleanup 방지)
  CREATED_IDS=()
  echo "  deleted and verified id=$RESOURCE_ID"
}

main() {
  init_logging "$ROOT/logs"
  require_env || exit 2
  install_cleanup_trap

  log_info "scenario=create_and_delete_instance base_url=\$BASE_URL (값 미출력)"

  try_step "Create Instance" create_instance
  try_step "Poll until ACTIVE" poll_until_status "$RESOURCE_ID" "ACTIVE"
  try_step "Validate Instance" validate_instance
  try_step "Delete Instance & Verify" delete_and_verify

  # 정상 완료 시 trap cleanup 무력화 (이미 삭제됨)
  trap - EXIT INT TERM
  print_summary
}

main "$@"
