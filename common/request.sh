#!/usr/bin/env bash
# API 요청 공통 래퍼 (원본 lib/http.sh 패턴을 일반화·비식별화)
# 결과 전역: HTTP_STATUS, HTTP_BODY, HTTP_TIME, HTTP_STDERR

set -euo pipefail

HTTP_BASE_OPTS=()
HTTP_HEADERS=()
_HTTP_META_PREFIX="___LIBHTTP_META_"
_HTTP_META_SUFFIX="___"

http_set_base_opts() {
  HTTP_BASE_OPTS=("$@")
}

http_set_headers() {
  HTTP_HEADERS=("$@")
}

# http_request METHOD URL [BODY]
# return: 2xx → 0, 그 외 → 1
http_request() {
  local method="$1"
  local url="$2"
  local body="${3:-}"

  local curl_bin="${CURL_PATH:-curl}"
  local stderr_file body_file=""
  stderr_file=$(mktemp) || return 1

  local -a cmd=("$curl_bin")
  cmd+=("${HTTP_BASE_OPTS[@]}")
  cmd+=("${HTTP_HEADERS[@]}")
  cmd+=(-X "$method")

  if [[ -n "$body" ]]; then
    body_file=$(mktemp) || { rm -f "$stderr_file"; return 1; }
    printf '%s' "$body" >"$body_file"
    cmd+=(-H "Content-Type: application/json" --data-binary "@$body_file")
  fi

  cmd+=(-w "\n${_HTTP_META_PREFIX}%{http_code}_%{time_total}${_HTTP_META_SUFFIX}\n")
  cmd+=("$url")

  local raw
  raw=$("${cmd[@]}" 2>"$stderr_file") || true

  if [[ -s "$stderr_file" ]]; then
    HTTP_STDERR=$(<"$stderr_file")
  else
    HTTP_STDERR=""
  fi
  rm -f "$stderr_file" "$body_file" 2>/dev/null || true

  local lastline
  lastline=$(printf '%s\n' "$raw" | tail -n1)
  HTTP_BODY=$(printf '%s\n' "$raw" | sed '$d')
  HTTP_STATUS=""
  HTTP_TIME=""

  local parsed
  parsed=$(printf '%s' "$lastline" | sed -n "s/.*${_HTTP_META_PREFIX}\([0-9]*\)_\([0-9.]*\)${_HTTP_META_SUFFIX}.*/\1 \2/p")
  if [[ -n "$parsed" ]]; then
    HTTP_STATUS="${parsed%% *}"
    HTTP_TIME="${parsed#* }"
  fi

  if [[ "$HTTP_STATUS" =~ ^2[0-9][0-9]$ ]]; then
    return 0
  fi
  return 1
}

# http_safe DESC METHOD URL [BODY]
# 성공 시 body stdout, 실패 시 진단 정보 stderr
http_safe() {
  local desc="$1"
  local method="$2"
  local url="$3"
  local body="${4:-}"

  if ! http_request "$method" "$url" "$body"; then
    echo "HTTP 실패 ($desc): 코드 ${HTTP_STATUS:-unknown}" >&2
    echo "  endpoint: $method $url" >&2
    if [[ -n "${HTTP_BODY:-}" ]]; then
      echo "  응답 일부:" >&2
      printf '%s\n' "$HTTP_BODY" | head -20 | sed 's/^/    /' >&2
    else
      echo "  (본문 없음)" >&2
    fi
    [[ -n "${HTTP_TIME:-}" ]] && echo "  elapsed: ${HTTP_TIME}s" >&2
    return 1
  fi
  printf '%s' "$HTTP_BODY"
  return 0
}

safe_jq() {
  local expr="$1"
  local input="${2:-}"
  local jq_bin="${JQ_PATH:-jq}"
  if [[ -n "$input" ]]; then
    printf '%s' "$input" | "$jq_bin" -r "$expr"
  else
    "$jq_bin" -r "$expr"
  fi
}

# Authorization 헤더 구성 (실토큰은 환경변수만)
apply_auth_headers() {
  HTTP_HEADERS=()
  if [[ -n "${API_TOKEN:-}" ]]; then
    HTTP_HEADERS+=(-H "Authorization: Bearer ${API_TOKEN}")
  fi
  HTTP_HEADERS+=(-H "Accept: application/json")
  http_set_base_opts -sS --connect-timeout "${CONNECT_TIMEOUT:-10}" --max-time "${MAX_TIME:-60}"
}
