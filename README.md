# Private Cloud API Test Automation

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

이 검증은 잘못된 응답에 대해 시나리오가 **실패하는지 확인**합니다. 실패를 무시하거나 xfail로 처리하지 않습니다.

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

## 데모 API 계약

- `POST /api/v1/instances`: `name`, `network`, `flavor`, `image`; 201 + `id/name/status`
- `GET /api/v1/instances/{id}`: 200 + `id/name/status`, 없으면 404
- `DELETE /api/v1/instances/{id}`: 성공 2xx, 이후 조회 404/410
- 선택 필드 `returnCode`가 있으면 `COMMON_OK`, `success`가 있으면 `true`여야 성공

로컬 서버는 생성 즉시 ACTIVE가 됩니다. 실제 클라우드의 처리 시간·상태 전환·인증을 재현하지 않습니다. 다른 API에는 URL과 토큰뿐 아니라 요청·응답 계약도 맞춰야 합니다.

## 업무 경험과 공개 범위

실무에서 사용한 공통 요청, 상태 관측, 단계별 결과, 리소스 ID 추적·정리 방식을 일반화했습니다. 전체 업무 시나리오, 자동 토큰 갱신 daemon, 환경 자동 조회, Kubernetes 비정상 Pod 시나리오는 이 공개 데모에 포함하지 않습니다.

사내·운영 자격증명, 내부 주소, 실제 리소스 ID와 실행 로그는 커밋하지 않습니다. 단순 성공 응답만으로 PASS를 만들지 않고, 실패 원인과 남은 자원을 다음 QA가 확인할 수 있도록 하는 데 초점을 둡니다.
