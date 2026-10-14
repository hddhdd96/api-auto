#!/usr/bin/env bash
# Call in the current shell; read HTTP_* after completion, including failures.
set -euo pipefail
HTTP_BASE_OPTS=()
HTTP_HEADERS=()
HTTP_STATUS='' HTTP_BODY='' HTTP_TIME='' HTTP_STDERR='' HTTP_CURL_EXIT=0

http_set_base_opts() { HTTP_BASE_OPTS=("$@"); }
http_set_headers() { HTTP_HEADERS=("$@"); }

http_request() {
  local method="$1" url="$2" body="${3:-}" scratch metadata
  HTTP_STATUS='' HTTP_BODY='' HTTP_TIME='' HTTP_STDERR='' HTTP_CURL_EXIT=0
  scratch=$(mktemp -d) || return 1
  local -a cmd=("${CURL_PATH:-curl}")
  cmd+=("${HTTP_BASE_OPTS[@]}" "${HTTP_HEADERS[@]}" -X "$method")
  if [[ -n "$body" ]]; then
    printf '%s' "$body" >"$scratch/request"
    cmd+=(-H 'Content-Type: application/json' --data-binary "@$scratch/request")
  fi
  metadata=$("${cmd[@]}" -o "$scratch/response" -w '%{http_code} %{time_total}' "$url" 2>"$scratch/stderr") || HTTP_CURL_EXIT=$?
  [[ ! -f "$scratch/response" ]] || HTTP_BODY=$(cat "$scratch/response")
  HTTP_STDERR=$(cat "$scratch/stderr")
  HTTP_STATUS="${metadata%% *}"
  HTTP_TIME="${metadata#* }"
  rm -rf "$scratch"
  ((HTTP_CURL_EXIT == 0)) || return 2
  [[ "$HTTP_STATUS" =~ ^2[0-9][0-9]$ ]]
}

http_safe() {
  local description="$1"
  shift
  if http_request "$@"; then
    printf '%s' "$HTTP_BODY"
    return 0
  fi
  printf '요청 실패: %s HTTP=%s curl=%s elapsed=%s\n' "$description" "${HTTP_STATUS:-unknown}" "$HTTP_CURL_EXIT" "$HTTP_TIME" >&2
  [[ -z "$HTTP_STDERR" ]] || printf '%s\n' "$HTTP_STDERR" >&2
  return 1
}

safe_jq() {
  printf '%s' "${2:-}" | "${JQ_PATH:-jq}" -r "$1"
}

apply_auth_headers() {
  HTTP_HEADERS=(-H 'Accept: application/json')
  [[ -z "${API_TOKEN:-}" ]] || HTTP_HEADERS+=(-H "Authorization: Bearer ${API_TOKEN}")
  http_set_base_opts -sS --connect-timeout "${CONNECT_TIMEOUT:-10}" --max-time "${MAX_TIME:-60}"
}
