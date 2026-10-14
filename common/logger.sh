#!/usr/bin/env bash
# 실행 로그 (원본 logger 패턴 단순화)

LOG_FILE="${LOG_FILE:-}"

init_logging() {
  local dir="${1:-logs}"
  mkdir -p "$dir"
  LOG_FILE=$(mktemp "$dir/run.XXXXXX") || return 1
  export LOG_FILE
  echo "로그 파일: $LOG_FILE"
}

log_info() {
  local msg="$*"
  local line="[INFO] $(date '+%F %T') $msg"
  echo "$line"
  if [[ -n "${LOG_FILE:-}" ]]; then echo "$line" >>"$LOG_FILE"; fi
}

log_fail() {
  local step="$1"
  shift
  local msg="$*"
  local line="[FAIL] $(date '+%F %T') step=$step $msg"
  echo "$line" >&2
  if [[ -n "${LOG_FILE:-}" ]]; then echo "$line" >>"$LOG_FILE"; fi
}

log_pass() {
  local step="$1"
  shift
  local msg="$*"
  local line="[PASS] $(date '+%F %T') step=$step $msg"
  echo "$line"
  if [[ -n "${LOG_FILE:-}" ]]; then echo "$line" >>"$LOG_FILE"; fi
}
