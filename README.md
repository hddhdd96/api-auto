# Private Cloud API Test Automation

[![CI](https://github.com/hddhdd96/api-auto/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/hddhdd96/api-auto/actions/workflows/ci.yml)

Shell + curl + jq로 클라우드 QA의 **생성 → 상태 검증 → 삭제 확인** 흐름을 공개용으로 재구성한 데모입니다. HTTP 요청 성공과 업무 결과, 최종 리소스 상태를 분리합니다.

## 바로 검증

필수 도구: Bash, curl, jq, Python 3.9 이상. Python은 로컬 합성 API와 회귀 검증에만 사용하며 추가 패키지가 필요하지 않습니다.

```bash
python3 -m unittest discover -s tests -v -f
```

검증마다 임의의 로컬 포트에 합성 서버를 시작하고 종료합니다. 회사 계정·외부 API·인터넷 연결은 필요하지 않습니다. `-f`는 첫 실패에서 중단합니다.

| 검증 | 기대 |
|---|---|
| HTTP 201 생성 | 호출한 셸에 HTTP 상태가 보존되고 생성·검증·삭제 성공 |
| HTTP 200 + 업무 실패 | 실패 종료, 반환된 ID는 정리 |
| 최종 ERROR / INACTIVE | ACTIVE로 오인하지 않고 실패 종료 |
| 다른 리소스 이름 | 상태가 ACTIVE여도 실패 |
| 삭제 실패 | 실패 종료, ID 보존, DELETE 자동 재시도 없음 |
| 통신 실패 | 이전 응답 초기화, curl 종료 코드 보존 |
| 네거티브 요청 23개 | 토큰 없음·필수 항목 누락·잘못된 타입·없는 ID 등에 401/400/404로 거절하고, 거절된 요청은 리소스를 만들거나 지우지 않음 |

이 검증은 잘못된 응답에 대해 시나리오가 **실패하는지 확인**합니다. 실패를 무시하거나 xfail로 처리하지 않습니다.

## CI 가드레일

`main` push와 모든 PR에서 GitHub Actions가 `python3 -m unittest discover -s tests -v -f`를 실행합니다. 정상 응답뿐 아니라 잘못된 응답에서 시나리오가 실패하는지까지 매번 확인합니다.

AI 코딩 도구가 실패한 테스트를 고치면서 제품 대신 판정 조건을 바꿔 PASS로 만드는 일을 실무에서 겪었습니다. 이 원칙을 리뷰 습관이 아니라 파이프라인이 강제하도록, PR 단계에서 `guardrail/check_test_weakening.py`(Python 3.9 이상, 표준 라이브러리만 사용)가 판정 코드 diff를 검사하고 의심 변경이 있으면 job을 실패시킵니다.

| 규칙 | 잡아내는 변경 (예) |
|---|---|
| TW01·TW02 | PR 전체에서 assertion·실패 경로 또는 테스트 케이스 순감소 (파일 간 이동은 허용) |
| TW03 | `@unittest.skip`, `@unittest.expectedFailure`, `skipTest` 추가 |
| TW04 | retry 증가 (`DELETE_RETRY=3` 같은 재시도 설정) |
| TW05 | 완전 일치 → 부분 일치 (`[[ "$status" == "$expected" ]]` → `== *"$expected"*`: `INACTIVE`도 통과, `assertEqual` → `assertGreaterEqual`) |
| TW06·TW09 | 기대값 변경, 허용 값 확대 (허용 HTTP 코드에 `202` 추가) |
| TW07·TW08 | 실패 전파 제거·실패 무시(`|| return 1` 삭제, `|| true`), `expect(true)` 같은 항상 참인 판정 |
| TW10·TW11 | 정확 일치 옵션 제거, 가드레일 규칙·범위·워크플로 자체 변경 |

의도한 변경(제품 사양 변경 등)이면 PR 설명에 근거를 적고 `test-change-approved` 라벨을 붙입니다. 이때 발견 사항은 경고로 남고 job은 통과합니다. `main` 브랜치는 이 검사(`test-weakening guardrail`)를 병합 전 필수 체크로 지정했습니다. 검사 범위는 `guardrail/scope.txt`에서 관리합니다.

```bash
python3 -m unittest discover -s guardrail -v        # 실제 코드를 변형한 약화 사례 11건 + 정상 변경 5건
python3 guardrail/check_test_weakening.py guardrail/examples/weaken-active-check.diff   # ACTIVE 폴링 비교를 glob 부분 일치로 변경 → exit 1
python3 guardrail/check_test_weakening.py --base origin/main                          # 현재 브랜치 검사
```

diff 기반 휴리스틱이므로 모든 약화를 잡지는 않습니다. 이 저장소의 과거 커밋에 적용해 오탐을 줄였고, 최종 판단은 사람이 diff와 근거를 보고 내립니다.

## API 계약 기반 네거티브 TC (AI 초안, 직접 검토 후 채택)

정상 흐름만으로는 "잘못된 요청을 서버가 제대로 거절하는가"를 확인하지 못합니다. 그래서 API 설명서를 바탕으로 일부러 틀린 요청을 보내는 테스트를 추가했습니다. 아이디어는 AI가 내고, 무엇을 테스트에 넣을지는 직접 검토해 정합니다.

1. **설명서 정리**: README의 데모 API 계약을 `contract/openapi.json`(OpenAPI)으로 옮겼습니다. README에 없는 부분(401, 400)은 서버 동작에서 가져왔고 항목마다 출처를 적었습니다.
2. **AI 초안**: 설명서만 AI(Claude)에게 주고 네거티브 요청 아이디어 27개를 받았습니다. 지시문은 `contract/prompts/`, 원본 초안은 `contract/drafts/2026-10-27-claude.json`에 그대로 있습니다.
3. **실행해 보기**: `python3 contract/check_drafts.py`가 초안을 데모 서버에 한 번씩 보내 실제 응답을 기록합니다(`*.results.json`).
4. **검토·채택**: 결과를 보고 채택·제외를 정해 `*.review.json`에 이유와 함께 남겼습니다.
5. **회귀 테스트**: 채택한 초안만 `tests/test_negative_contract.py`가 실행합니다. 응답 코드와 함께, 거절된 요청이 리소스를 만들거나 지우지 않았는지도 확인합니다.

| 항목 | 수 |
|---|---|
| AI 초안 | 27 |
| 채택 | **23** (설명서대로 동작 18 + 불일치 수정 후 5) |
| 제외 | 4 (설명서에 정답이 없어 요구사항 확인 필요) |
| 새로 검사하게 된 조건 | 23 (기존 테스트에는 네거티브 요청 검사가 없었음) |
| 발견한 설명서-서버 불일치 | **5** |

**발견한 불일치.** README는 `network`, `flavor`, `image`를 필수 항목으로 적었지만 서버는 `name`만 검사했습니다. 세 항목을 빼거나 숫자·배열을 넣어도 생성에 성공(201)했습니다. 실무라면 결함으로 등록할 내용이며, 데모 서버를 설명서에 맞게 고친 뒤 테스트로 고정했습니다.

**요구사항 확인 필요(제외한 4개).** 설명서에 정답이 없어 임의로 정하지 않았습니다. 현재 서버는 모두 생성에 성공합니다.

- 이름 최대 길이는 몇 자인가? (1만 자 이름)
- 공백만 있는 이름을 허용하는가?
- `network` 빈 문자열을 허용하는가?
- 설명서에 없는 항목이 오면 무시하는가, 거절하는가?

## 데모를 단계별로 실행

터미널 1:

```bash
python3 demo/server.py
```

터미널 2:

```bash
BASE_URL=http://127.0.0.1:8766 API_TOKEN=demo-token bash scripts/run.sh
```

`demo-token`은 로컬 합성 서버의 공개 예제 문자열입니다. 실제 자격증명이 아닙니다. `.env` 없이 환경변수로 실행할 수 있고, 필요하면 `.env.example`을 복사합니다. 이름을 생략하면 실행별 이름을 생성합니다.

## 핵심 구현

### 요청 결과 보존

`http_request`는 현재 셸에서 호출하고 `HTTP_STATUS`, `HTTP_BODY`, `HTTP_TIME`, `HTTP_STDERR`, `HTTP_CURL_EXIT`를 읽습니다. 본문은 임시 파일로 분리해 JSON 내부 문자열이 메타데이터로 해석되지 않게 합니다.

```bash
http_safe get-instance GET "$url" >/dev/null || return 1
assert_http_status 200 get_http || return 1
assert_business_success "$HTTP_BODY" || return 1
```

`body=$(http_safe ...)` 뒤 부모 셸의 HTTP 상태를 읽지 않습니다. HTTP 성공이어도 응답의 `returnCode` 또는 `success`가 실패를 나타내면 FAIL입니다.

### 정확한 리소스 판정

생성은 200/201을 허용하고 ID를 추적합니다. 폴링은 `BUILD`/`CREATING`에서만 관측을 이어가며, `ACTIVE` 완전 일치만 성공입니다. HTTP 오류·잘못된 JSON·다른 상태는 실패합니다. 최종 조회는 ID·name·status를 함께 검증합니다.

### 실패 후 정리와 원인 보존

반환된 ID는 후속 assertion 전에 기록합니다. EXIT에서 정리를 수행하며 원래 실패 종료 코드를 유지합니다. 삭제 요청·조회에서 오류가 나면 자동 재요청하지 않습니다. 정상 삭제 후 조회에서 404/410을 확인한 ID만 추적에서 제거합니다.

`logs/run.*.resources.json`에 잔여 ID가 남으며, 정리 실패는 성공 실행으로 표시하지 않습니다. 생성 요청 결과에 ID가 없거나 응답 자체를 받지 못한 경우에는 로그의 고유 이름으로 수동 확인해야 합니다. 서버 측 idempotency나 불명확한 생성 요청 재전송은 구현하지 않았습니다.

## 구조

| 경로 | 책임 |
|---|---|
| `common/request.sh` | curl 결과와 전송 오류 보존 |
| `common/assertion.sh` | HTTP·JSON 업무 결과·필드 assertion, 단계 집계 |
| `common/polling.sh` | 최종 상태 확인과 오류·시간 제한 처리 |
| `common/cleanup.sh` | 실행별 자원 추적, 삭제 검증, 종료 시 정리 |
| `common/logger.sh` | 실행별 로그 |
| `scenarios/compute/create_and_delete_instance.sh` | Instance lifecycle |
| `config/env.sh`, `data/` | 실행 설정·jq로 안전하게 채우는 요청 본문 |
| `demo/server.py` | 로컬 합성 API |
| `tests/test_contract.py` | 정상·실패 응답에 대한 회귀 계약 |
| `contract/` | API 계약(OpenAPI), AI 네거티브 TC 초안·검토 기록, 초안 실행 스크립트 |
| `tests/test_negative_contract.py` | 검토에서 채택한 네거티브 요청 회귀 테스트 |

## 데모 API 계약

- `POST /api/v1/instances`: `name`, `network`, `flavor`, `image`; 201 + `id/name/status`
- `GET /api/v1/instances/{id}`: 200 + `id/name/status`, 없으면 404
- `DELETE /api/v1/instances/{id}`: 성공 2xx, 이후 조회 404/410
- 선택 필드 `returnCode`가 있으면 `COMMON_OK`, `success`가 있으면 `true`여야 성공

로컬 서버는 생성 즉시 ACTIVE가 됩니다. 실제 클라우드의 처리 시간·상태 전환·인증을 재현하지 않습니다. 다른 API에는 URL과 토큰뿐 아니라 요청·응답 계약도 맞춰야 합니다.

## 업무 경험과 공개 범위

실무에서 사용한 공통 요청, 상태 관측, 단계별 결과, 리소스 ID 추적·정리 방식을 일반화했습니다. 전체 업무 시나리오, 자동 토큰 갱신 daemon, 환경 자동 조회, Kubernetes 네거티브 시나리오는 이 공개 데모에 포함하지 않습니다.

사내·운영 자격증명, 내부 주소, 실제 리소스 ID와 실행 로그는 커밋하지 않습니다. 단순 성공 응답만으로 PASS를 만들지 않고, 실패 원인과 남은 자원을 다음 QA가 확인할 수 있도록 하는 데 초점을 둡니다.
