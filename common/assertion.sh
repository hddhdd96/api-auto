#!/usr/bin/env bash
# 스텝 단위 PASS/FAIL (원본 try_step / cb_step_* 패턴 일반화)

TOTAL=0
PASS=0
FAIL=0
FAILED_STEPS=()

assert_http_status() {
  local expected="$1"
  local actual="${HTTP_STATUS:-}"
  local step="${2:-http_status}"
  if [[ "$actual" != "$expected" ]]; then
    log_fail "$step" "HTTP expected=$expected actual=${actual:-empty} endpoint=${LAST_ENDPOINT:-?} elapsed=${HTTP_TIME:-?}"
    [[ -n "${HTTP_BODY:-}" ]] && printf '%s\n' "$HTTP_BODY" | head -10 | sed 's/^/  body> /' >&2
    return 1
  fi
  return 0
}

assert_jq_equals() {
  local expr="$1"
  local expected="$2"
  local body="$3"
  local step="${4:-body_assert}"
  local actual
  actual=$(safe_jq "$expr" "$body")
  if [[ "$actual" != "$expected" ]]; then
    log_fail "$step" "jq '$expr' expected=$expected actual=${actual:-empty}"
    return 1
  fi
  return 0
}

# try_step TITLE -- command...
# 원본: TC id + 제목 + 토큰 보장 후 명령 실행. 포트폴리오에서는 제목+명령만 유지.
try_step() {
  local title="$1"
  shift
  ((TOTAL++)) || true
  echo ""
  echo "==== [STEP] $title ===="
  export CURRENT_STEP="$title"
  if "$@"; then
    ((PASS++)) || true
    log_pass "$title" "ok"
    return 0
  else
    ((FAIL++)) || true
    FAILED_STEPS+=("$title")
    log_fail "$title" "failed (http=${HTTP_STATUS:-?} resource=${RESOURCE_ID:-?} status=${RESOURCE_STATUS:-?})"
    return 1
  fi
}

print_summary() {
  echo ""
  echo "======== SUMMARY ========"
  echo "total=$TOTAL pass=$PASS fail=$FAIL"
  if ((${#FAILED_STEPS[@]} > 0)); then
    echo "failed steps:"
    printf '  - %s\n' "${FAILED_STEPS[@]}"
  fi
  ((FAIL == 0))
}
