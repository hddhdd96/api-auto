# Playwright QA 자동화 포트폴리오

## Overview

실제 업무에서 웹 기반 클라우드 플랫폼의 E2E 자동화를 설계하고 운영한 경험을 바탕으로, 프로젝트 구조와 설계 방식을 일반화해 구성한 샘플입니다. 실제 회사 소스 코드와 제품 정보는 공개하지 않습니다.

## Project Goals

- 도메인별 테스트 시나리오와 재사용 가능한 UI 동작을 분리합니다.
- 테스트 데이터, 인증 상태, 환경 설정과 실행 결과를 각각 관리합니다.
- 실패 원인을 추적할 수 있도록 Playwright 증적과 HTML 리포트를 구성합니다.
- 실제 대상 시스템이 없어도 구조와 테스트 설계를 빠르게 이해할 수 있게 합니다.

## Tech Stack

TypeScript · Node.js · npm · Playwright Test · Playwright HTML Reporter

## Project Architecture

```text
Playwright setup → auth/storageState.json → fixture → test suite
                                              ├── test case
                                              ├── page object
                                              ├── test data
                                              └── evidence / manifest utilities
```

## Directory Structure

```text
ui-auto/
├── auth/
│   └── auth.setup.ts             # 한 번 로그인하고 storageState 저장
├── codegen-output/               # Codegen 산출물 위치 (샘플 안내만 추적)
├── config/                       # 테스트 스위트와 실행 도구 설정 문서
├── data/
│   └── volume-test-data.ts        # Volume 테스트 입력 데이터
├── docs/                         # 아키텍처, locator, 테스트 명세
├── fixtures/
│   └── base-test.ts              # 공통 Playwright fixture와 Page Object
├── pages/
│   ├── BasePage.ts                # 공통 Page Object 기반
│   ├── auth/LoginPage.ts          # 로그인 동작 캡슐화
│   ├── basic-settings/            # 공통 설정 페이지 객체 위치
│   ├── components/               # 재사용 UI 컴포넌트
│   ├── compute/                  # Instance 페이지 객체 위치
│   ├── management/               # 관리 화면 페이지 객체 위치
│   ├── monitoring/               # 모니터링 페이지 객체 위치
│   ├── network/                  # 네트워크 페이지 객체 위치
│   └── storage/VolumePage.ts      # Volume 동작과 검증
├── scripts/                      # 로컬·CI 실행 보조 스크립트 위치
├── tests/
│   ├── testcase/                 # 도메인별 작은 생성·삭제 흐름
│   │   ├── 01-pre/{create,delete}/
│   │   ├── 02-compute/{create,delete}/
│   │   ├── 03-storage/{create,delete}/
│   │   ├── 04-network/{create,delete}/
│   │   └── 05-cluster/{create,delete}/
│   ├── testsuite/                # Playwright 실행 spec
│   │   └── 03-storage/volume-lifecycle.spec.ts
│   └── unit/                     # 공통 로직 단위 테스트
│       └── volume-test-data.spec.ts
├── tools/                        # 테스트 문서·데이터 보조 도구 위치
├── utils/
│   ├── manifest/                 # 실행 리소스 상태 관리 위치
│   ├── evidence-recorder.ts      # 체크포인트 스크린샷 첨부
│   └── test-logger.ts            # 테스트 로그
├── .env.example
├── package.json
├── playwright.config.ts
└── tsconfig.json
```

| 경로 | 역할과 분리 이유 |
| --- | --- |
| `tests/testsuite/` | 테스트 실행 단위를 정합니다. 어떤 흐름을 실행하는지 spec만 읽어도 알 수 있습니다. |
| `tests/testcase/` | 기능별 준비·생성·삭제 흐름을 나누어 여러 suite에서 재사용할 수 있습니다. |
| `pages/` | locator, 사용자 동작, 페이지 수준 검증을 캡슐화해 UI 변경의 영향을 줄입니다. |
| `fixtures/` | Page Object를 테스트에 주입해 생성 코드를 중복하지 않습니다. |
| `data/` | 입력값을 테스트 코드에서 분리해 시나리오가 의도를 드러내게 합니다. |
| `auth/` | 로그인 준비와 인증 파일의 생명주기를 분리합니다. 인증 상태 파일은 Git에서 제외합니다. |
| `utils/` | 증적, 로그, 실행 리소스 상태 등 횡단 관심사를 재사용합니다. |
| `config/`, `docs/` | 환경별 설정과 운영 설명을 테스트 구현에서 분리합니다. |

## Test Scenario

샘플은 다음 Volume 수명주기를 한 테스트에서 확인합니다.

```text
로그인 → Storage 메뉴 이동 → Volume 생성 → 상태 확인
       → 상세 정보 검증 → Volume 삭제 → 목록에서 제거 확인
```

실제 업무에서도 로그인부터 리소스 생성·검증·삭제까지 이어지는 웹 기반 클라우드 플랫폼 E2E 시나리오를 자동화했습니다. 여기의 `Volume`, locator와 화면 문구는 동작 방식을 설명하기 위한 일반 예시입니다.

## Automation Design

- Page Object는 locator와 페이지 단위 동작·검증만 담당합니다.
- Fixture는 Page Object를 테스트에 주입하고 공통 설정 지점을 제공합니다.
- 테스트 데이터 생성은 `data/`에서 수행해 시나리오 코드와 입력값을 분리합니다.
- locator는 role과 label을 우선 사용하고, 실제 UI에서 확인된 경우에만 구현합니다.
- 고정 대기 없이 Playwright assertion과 자동 대기로 화면 상태를 확인합니다.
- 샘플 UI locator는 제품 계약이 아니므로 실제 화면에 맞춰 검증해야 합니다.

## Authentication

`auth/auth.setup.ts`가 `.env`의 인증값으로 한 번 로그인하고 `auth/storageState.json`을 저장합니다. E2E 프로젝트는 이 파일을 사용해 매 테스트마다 로그인하지 않습니다. 저장 상태에는 쿠키와 토큰이 들어갈 수 있어 `.gitignore`에 포함했습니다. 저장소에는 실제 인증 상태 파일이 없습니다.

## Test Execution

폐쇄망에서는 승인된 npm 캐시나 패키지 미러에서 의존성을 설치합니다. 실행 전 `.env.example`을 `.env`로 복사하고 허가된 테스트 환경값을 설정합니다.

```bash
npm install
npx playwright install chromium
npm run test:e2e
npm run test:unit
```

예시 URL은 `https://example.com`이며 인증값은 자리표시자입니다. 이 샘플은 실제 제품 화면과 서비스 동작을 보장하지 않습니다.

## Test Report

- Playwright HTML Reporter 결과: `playwright-report/`
- 실패 스크린샷, trace, video: `test-results/`
- 검증 지점 스크린샷: 테스트 첨부 항목

생성된 파일은 `.gitignore`에 포함되며 고객 환경 증적을 공개 저장소에 올리지 않습니다.

## Key QA Engineering Points

- 단순 Record & Playback에 머물지 않고 장기 유지보수가 가능한 역할 분리를 적용했습니다.
- Page Object Model로 locator와 화면 동작 변경을 한곳에서 관리합니다.
- Fixture로 공통 객체 생성과 실행 설정을 관리합니다.
- 테스트 데이터와 테스트 흐름을 분리해 재사용과 병렬 실행을 돕습니다.
- `storageState`로 인증 흐름을 재사용하고 로그인 중복을 줄입니다.
- Playwright 자동 대기와 명시적 assertion으로 고정 대기 의존을 피합니다.
- 접근성 locator를 우선하고 locator 변경 지점을 Page Object에 모읍니다.
- 실패 시 screenshot, trace, video를 사용해 원인을 분석할 수 있습니다.
- 테스트 케이스와 실행 suite를 분리해 도메인과 실행 범위를 확장하기 쉽게 합니다.

## Repository Notice

이 저장소는 QA 자동화 설계 경험과 프레임워크 구조를 보여주는 포트폴리오 샘플입니다. 보안과 회사 자산 보호를 위해 실제 업무 코드, 회사명, 제품명, 고객사명, 내부 URL/IP, 계정, API 정보와 실행 증적은 공개하지 않았습니다. 코드 구조와 예시 locator는 개념 설명용이며 실제 서비스 접속용이 아닙니다.
