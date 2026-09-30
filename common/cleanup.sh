#!/usr/bin/env bash
# 생성 리소스 정리 (원본 delete verify 패턴 단순화)

CREATED_IDS=()

track_resource() {
  CREATED_IDS+=("$1")
}

# delete 후 목록/상세에서 사라질 때까지 대기
wait_resource_deleted() {
  local resource_id="$1"
  local max_sec="${2:-${TIMEOUT_DELETE:-120}}"
  local interval="${3:-${POLL_INTERVAL:-5}}"
  local elapsed=0
  local url="${BASE_URL}/api/v1/instances/${resource_id}"

  while (( elapsed <= max_sec )); do
    apply_auth_headers
    export LAST_ENDPOINT="GET $url"
    if http_request GET "$url"; then
      # 아직 존재
      echo "  delete-verify: still present id=$resource_id http=$HTTP_STATUS"
    else
      # 404 등 → 삭제된 것으로 간주
      if [[ "${HTTP_STATUS:-}" == "404" || "${HTTP_STATUS:-}" == "410" ]]; then
        echo "  delete-verify: gone id=$resource_id http=$HTTP_STATUS"
        return 0
      fi
      # 기타 오류는 계속 재시도하지 않고 기록
      echo "  delete-verify: unexpected http=$HTTP_STATUS id=$resource_id"
    fi
    sleep "$interval"
    elapsed=$((elapsed + interval))
  done
  log_fail "cleanup" "delete verify timeout id=$resource_id"
  return 1
}

delete_instance() {
  local resource_id="$1"
  local url="${BASE_URL}/api/v1/instances/${resource_id}"
  apply_auth_headers
  export LAST_ENDPOINT="DELETE $url"
  if ! http_safe "delete-instance" DELETE "$url" >/dev/null; then
    # 이미 없으면 성공 처리
    if [[ "${HTTP_STATUS:-}" == "404" ]]; then
      return 0
    fi
    return 1
  fi
  wait_resource_deleted "$resource_id"
}

cleanup_tracked() {
  local id
  for id in "${CREATED_IDS[@]:-}"; do
    [[ -z "$id" ]] && continue
    echo "cleanup: deleting $id"
    delete_instance "$id" || echo "cleanup warn: failed to delete $id" >&2
  done
  CREATED_IDS=()
}

# 테스트 실패/중단 시에도 정리 시도
install_cleanup_trap() {
  trap 'echo ""; echo "[trap] running cleanup..."; cleanup_tracked' EXIT INT TERM
}
