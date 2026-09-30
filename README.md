# Private Cloud API Test Automation

This repository is a sanitized reconstruction of API automation used in a private cloud QA environment.

Private Cloud(IaaS) 환경에서 수행한 **REST API 기능 검증·반복 테스트 자동화**를, 사내·고객·인프라 정보를 제거한 뒤 공개용으로 재구성한 프로젝트입니다.

실제 회사명, 제품명, 고객 환경, 내부 URL/IP, 자격증명, 실제 API 경로·리소스명·요청 데이터는 포함하지 않습니다.

---

## Overview

콘솔과 수동 API 호출로 리소스를 만들고, 상태가 안정될 때까지 확인한 뒤 검증·삭제하는 작업이 반복되던 흐름을 Shell + curl + jq로 자동화했습니다.

이 저장소는 전체 제품·시나리오를 그대로 옮긴 것이 아니라, 평가자가 구조를 빠르게 파악할 수 있도록 **Compute Instance 수명주기(생성 → 상태 대기 → 검증 → 삭제)** 한 줄기를 중심으로 정리했습니다.

---

## What it solves

- 동일 API 시나리오의 반복 실행
- 리소스 생성·삭제와 ID 추적
- 생성 직후 완료되지 않는 리소스의 상태 확인(폴링)
- HTTP 상태·응답 본문의 반복 육안 확인 감소
- 실패 지점을 로그로 좁혀 원인 분석 시간 단축

---

## Tech Stack

| Stack | Role |
|---|---|
| Bash | 시나리오·공통 라이브러리 |
| curl | REST API 호출 |
| jq | 응답 파싱·필드 검증 |
| `.env` | Base URL, 토큰, 타임아웃 |
| Linux | 실행 환경 |

---

## Project Structure

```text
.
├── common/
│   ├── request.sh      # curl 래퍼, HTTP status / elapsed 분리
│   ├── assertion.sh    # step 실행, HTTP·Body 검증, 결과 집계
│   ├── polling.sh      # 비동기 상태 폴링 (예: BUILD → ACTIVE)
│   ├── cleanup.sh      # 삭제 및 삭제 확인, 중단 시 정리
│   └── logger.sh       # PASS / FAIL / INFO 로그
├── scenarios/
│   └── compute/
│       └── create_and_delete_instance.sh
├── config/
│   └── env.sh
├── data/
│   └── create_instance.json
├── scripts/
│   └── run.sh
├── logs/
├── .env.example
└── README.md
```

| Path | Responsibility |
|---|---|
| `common/` | 요청·검증·폴링·정리 등 재사용 계층 |
| `scenarios/` | 비즈니스 흐름(시나리오)만 기술 |
| `config/` | 환경변수 로드 |
| `data/` | 요청 본문 템플릿(예시 값) |
| `scripts/run.sh` | 실행 진입점 |

---

## Test Flow

```text
Load .env → Auth header
        ↓
Create Instance (POST)
        ↓
Validate HTTP (200 / 201) → extract Resource ID
        ↓
Poll status until ACTIVE
  (BUILD → BUILD → ACTIVE | ERROR | TIMEOUT)
        ↓
GET + body validation (status == ACTIVE)
        ↓
Delete Instance
        ↓
Verify deletion (404 / 410)
```

시나리오 실행 중 실패하거나 중단되면, 추적 중인 리소스에 대해 cleanup을 시도합니다.

---

## Key Design

### Request wrapper

`common/request.sh`의 `http_request`는 curl `-w`로 **HTTP status**와 **소요 시간**을 body와 분리합니다.  
`http_safe`는 실패 시 step 설명, HTTP 코드, endpoint, 응답 일부, elapsed를 남깁니다.

### Step execution

`try_step`으로 단계를 나누어 실행하고 PASS/FAIL과 실패 step 목록을 집계합니다.

### Polling

Private Cloud 인스턴스는 생성 API 성공만으로 사용 가능 상태가 아닙니다.  
상세 조회를 반복하며 `ACTIVE`를 기다리고, `ERROR`면 즉시 실패, 제한 시간 초과 시 timeout 처리합니다.

### Cleanup

생성 시 Resource ID를 추적하고, 삭제 후 GET이 404/410이면 삭제로 간주합니다.

### Configuration

`BASE_URL`, `API_TOKEN`, 타임아웃은 `.env`만 사용합니다. 저장소에는 `.env.example`만 포함합니다.

---

## Scenario

**Compute Instance lifecycle**

1. 예시 JSON으로 Instance 생성  
2. ID 저장 후 `ACTIVE`까지 폴링  
3. GET으로 상태 재확인  
4. 삭제 후 삭제 확인  

요청·리소스 이름은 모두 일반화되어 있습니다 (`qa-test-instance`, `qa-test-network`, `/api/v1/instances`).

---

## How to Run

필수 도구: `bash`, `curl`, `jq`, `envsubst` (gettext)

```bash
cp .env.example .env
# .env 에 BASE_URL, API_TOKEN 설정

chmod +x scripts/run.sh
./scripts/run.sh
```

공개용 예시 엔드포인트에는 실제 서비스가 연결되어 있지 않을 수 있습니다.  
로컬·개인 테스트 환경의 Base URL과 토큰을 넣어 실행하세요. 사내·운영 자격증명은 사용하지 마세요.

---

## Confidentiality

- 회사명 / 고객사명 / 제품명 → 제거 또는 일반화
- 내부 URL, Domain, IP, Port → `$BASE_URL`
- Token, Password, API Key, Cookie → `$API_TOKEN` 등
- 실제 Endpoint·리소스명·Request Body → 예시 값으로 대체
- 인증서, 실행 로그, 실환경 ID 파일 → 미포함

This repository is a sanitized reconstruction of API automation used in a private cloud QA environment.
