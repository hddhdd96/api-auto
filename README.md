# Private Cloud API 테스트 자동화 (포트폴리오)

This repository is a sanitized reconstruction of API automation used in a private cloud QA environment.

실제 Private Cloud(IaaS) 환경에서 수행하던 **API 기반 기능 검증·반복 테스트 자동화** 경험을, 회사·고객·인프라 정보를 제거한 뒤 공개용으로 재구성한 프로젝트입니다.

> 실제 회사명, 제품명, 고객 환경, 내부 URL/IP, 자격증명, 실제 API 경로·리소스명·요청 데이터는 포함하지 않습니다.

---

## Project Overview

현장에서는 콘솔/수동 API 호출로 리소스를 만들고 상태가 끝날 때까지 기다린 뒤 검증·삭제하는 작업이 반복되었습니다.  
이 자동화는 그 흐름을 Shell + curl + jq로 묶어, **동일 시나리오를 반복 실행**하고 **실패 지점을 로그로 좁히기** 위해 만들었습니다.

본 저장소는 원본 전체(다수 제품·수백 시나리오)가 아니라, 포트폴리오에서 설명하기 좋은 **대표 흐름 하나(Compute Instance: 생성 → 폴링 → 검증 → 삭제)** 중심으로 구조를 드러냅니다.

---

## Background (자동화로 풀려던 문제)

원본 업무에서 확인된  sor:

- 동일 API 시나리오의 **반복 실행**
- 리소스 **다수 생성·삭제**와 ID 추적
- 생성 직후 완료되지 않는 리소스의 **수동 상태 확인**
- Request/Response·HTTP 코드의 **반복 육안 확인**
- 위 과정으로 인한 **검증 시간 증가**

---

## Tech Stack

원본·재구성본에서 **실제로 사용하는** 기술만 적습니다.

| 기술 | 용도 |
|---|---|
| Shell Script (Bash) | 시나리오·공통 라이브러리 |
| curl | REST API 호출 |
| jq | 응답 파싱·필드 검증 |
| 환경변수 (`.env`) | Base URL·토큰·타임아웃 |
| Linux | 실행 환경 |

다음 항목은 **현재 공개용 재구성본 / 원본 핵심 경로에서 포트폴리오 범위로 확인·포함하지 않음**:

- CI/CD 파이프라인 — 현재 프로젝트에서 확인되지 않음 (공개본 기준)
- Docker 기반 실행 — 현재 프로젝트에서 확인되지 않음
- 테스트 병렬 실행 프레임워크 — 현재 프로젝트에서 확인되지 않음
- Python/JS 테스트 러너 — 원본 핵심도 Shell 중심
- 상용 logging framework — 현재 프로젝트에서 확인되지 않음 (Shell 로그 함수 사용)

---

## Architecture

```text
api-automation/   (이 저장소 루트)
├── common/
│   ├── request.sh      # curl 래퍼, HTTP status/time 분리, http_safe
│   ├── assertion.sh    # try_step, HTTP/Body assert, 요약
│   ├── polling.sh      # 상태 폴링 (예: BUILD → ACTIVE)
│   ├── cleanup.sh      # 삭제 + 삭제 확인, 실패 시 trap cleanup
│   └── logger.sh       # PASS/FAIL/INFO 로그 파일
├── scenarios/
│   └── compute/
│       └── create_and_delete_instance.sh
├── config/
│   └── env.sh          # .env 로드
├── data/
│   └── create_instance.json   # 예시 요청 템플릿 (가짜 값)
├── scripts/
│   └── run.sh
├── logs/               # 실행 로그 (gitignore)
├── .env.example
└── README.md
```

원본은 제품별 메뉴·대량 create/delete·리포트 머지까지 포함한 대형 구조였습니다.  
공개본은 **읽히는 구조**를 위해 대표 시나리오와 공통 레이어만 남겼습니다.

---

## API Test Flow

```text
Load .env / Auth header
         ↓
Create Instance (POST)
         ↓
Validate HTTP (200/201) + 추출 Resource ID
         ↓
Poll Resource Status  (예: BUILD → BUILD → ACTIVE)
         ↓
GET + Body 검증 (status == ACTIVE)
         ↓
Delete Instance
         ↓
Verify Deletion (404/410 등)
```

실패·중단 시 `EXIT` trap으로 추적 중인 리소스 삭제를 시도합니다.  
(원본도 delete 시나리오·검증 폴링이 있으나, **모든 실패 경로의 강제 rollback이 단일 trap으로 통일되어 있지는 않았습니다.** 공개본에서는 대표 시나리오에 trap cleanup을 명시적으로 넣었습니다.)

---

## Key Implementation

### 1) API request wrapper (`common/request.sh`)

원본 `http_request`와 같이 curl `-w` 메타로 **HTTP 코드·소요 시간**을 body와 분리합니다.

```bash
http_request() {
  # ...
  cmd+=(-w "\n___LIBHTTP_META_%{http_code}_%{time_total}___\n")
  # HTTP_STATUS, HTTP_BODY, HTTP_TIME 설정
}
```

실패 시 `http_safe`가 **step 설명·HTTP 코드·endpoint·응답 일부·elapsed**를 남깁니다.

### 2) Step 실행 (`common/assertion.sh`)

원본 `try_step`처럼 단계 단위로 실행하고 PASS/FAIL·실패 step 목록을 집계합니다.

### 3) Polling (`common/polling.sh`) — 원본에서 확인된 핵심

Private Cloud 인스턴스는 생성 직후 바로 완료되지 않습니다. 원본 Compute 자동화는 상세 조회를 반복하며 상태가 `ACTIVE`가 될 때까지 기다리고, `ERROR`면 즉시 실패, 제한 시간 초과 시 timeout 처리했습니다.

```text
BUILD
 ↓
BUILD
 ↓
ACTIVE   (또는 ERROR / TIMEOUT)
```

### 4) Cleanup / Delete verify (`common/cleanup.sh`)

원본 delete 검증은 목록/상세 조회로 **리소스가 사라졌는지 폴링**합니다. 공개본은 GET이 404/410이면 삭제로 간주합니다.

### 5) Config

`BASE_URL`, `API_TOKEN`, 타임아웃은 `.env`만 사용합니다. 저장소에는 `.env.example`만 둡니다.

---

## Scenario

**Compute Instance 수명주기 검증**

1. 예시 JSON으로 Instance 생성  
2. ID 저장 후 ACTIVE까지 폴링  
3. GET으로 상태 재확인  
4. 삭제 후 삭제 확인  

요청 예시는 모두 일반화된 이름입니다 (`qa-test-instance`, `qa-test-network`, `/api/v1/instances`).

---

## How to Run

```bash
cp .env.example .env
# .env 에 BASE_URL, API_TOKEN 설정 (실운영/사내 값 사용 금지 권장)

chmod +x scripts/run.sh
./scripts/run.sh
```

필요 도구: `bash`, `curl`, `jq`, `envsubst`(gettext)

> 공개용 엔드포인트가 없으면 실행은 실패하는 것이 정상입니다.  
> 이 저장소의 목적은 **실무에서 쓰던 구조·검증·폴링 방식을 코드로 보여주는 것**입니다.

---

## Confidentiality

- 회사명 / 고객사명 / 제품명: 제거 또는 일반화
- 내부 URL, Domain, IP, Port: 제거 → `$BASE_URL`
- Token, Password, API Key, Cookie: 제거 → `$API_TOKEN` 등
- 실제 Endpoint·리소스명·Request Body 실데이터: 예시 값으로 대체
- 인증서(`.pem`/`.pfx`), 실행 로그·결과 CSV: 포함하지 않음

This repository is a sanitized reconstruction of API automation used in a private cloud QA environment.

---

## 면접에서 설명하기 좋은 포인트

1. **왜 Shell+curl+jq인가** — 고객/폐쇄망에서 추가 런타임 없이 바로 돌리기 쉬움  
2. **비동기 리소스 폴링** — CREATE 성공 ≠ 사용 가능. ACTIVE/ERROR/timeout을 나눔  
3. **실패 진단 정보** — HTTP status, body snippet, endpoint, resource id, step 이름, elapsed  
4. **ID 추적과 cleanup** — 생성 ID를 저장해 삭제·재실행 시 잔존 리소스 문제 완화  
5. **공통 레이어와 시나리오 분리** — request/assert/poll을 재사용하고 시나리오는 흐름만 기술

---

## 원본에서 확인된 기능 vs 공개본 개선

| 항목 | 원본에서 확인 | 공개본 |
|---|---|---|
| curl + jq REST 호출 | ✅ | ✅ 유지 |
| HTTP status / time 분리 | ✅ | ✅ 유지 |
| try_step 단위 PASS/FAIL | ✅ | ✅ 단순화 |
| Instance ACTIVE 폴링 | ✅ | ✅ 유지 |
| Delete 후 존재 여부 폴링 | ✅ | ✅ 단순화 |
| Token 자동 갱신 데몬 | ✅ | ❌ 미포함 (비밀·내부인증 의존) — **개선 제안**으로만 언급 |
| 대량 배치·메뉴 UI·TC 리포트 CSV | ✅ | ❌ 미포함 (포트폴리오 범위 축소) |
| 실패 시 전역 trap cleanup | 부분적 | ✅ 대표 시나리오에 명시 |
| CI/CD · Docker · 병렬 실행 | 확인되지 않음 | 넣지 않음 |

### 추가하면 좋은 개선사항 (아직 없음)

- 토큰 만료 임박 시 갱신(공개 가능한 mock auth 기준)
- dry-run / mock server로 로컬 데모 실행
- JUnit·간단한 HTML 리포트
- GitHub Actions에서의 smoke (mock 서버 대상)

---

## License / 사용 목적

개인 포트폴리오·면접 설명용입니다. 실서비스 트래픽이나 사내 자격증명과 연결하지 마세요.
