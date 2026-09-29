# UI 자동화 구조

```text
auth.setup.ts → auth/storageState.json → Playwright fixture → 테스트 스위트
                                                          ├── testcase 흐름
                                                          ├── 페이지 객체
                                                          └── 증적 / manifest 유틸리티
```

| 경로 | 책임과 분리 이유 |
| --- | --- |
| `tests/testcase/` | 작은 업무 흐름을 생성·삭제 단계와 도메인별로 관리해 재사용하기 쉽습니다. |
| `tests/testsuite/` | testcase를 Playwright 실행 단위로 묶어 실행 범위를 선택하기 쉽습니다. |
| `tests/unit/` | 브라우저가 필요 없는 유틸리티 검증을 E2E와 분리합니다. |
| `pages/` | UI locator와 페이지 동작을 캡슐화해 화면 변경의 영향을 한곳에 모읍니다. |
| `fixtures/` | 테스트별 페이지 객체를 제공해 생성 코드를 반복하지 않습니다. |
| `data/` | 테스트 입력값을 테스트 흐름과 분리해 시나리오를 읽기 쉽게 합니다. |
| `auth/` | 로그인 준비와 인증 상태 파일의 위치를 분리합니다. 인증 상태 파일은 Git에서 제외합니다. |
| `utils/` | 증적, 로깅, 리소스 manifest처럼 여러 테스트가 공유하는 처리를 담당합니다. |
| `config/`, `docs/` | 실행 설정과 운영·locator·테스트 명세를 코드에서 분리합니다. |

접근성 기반 locator와 Playwright 자동 대기를 우선합니다. `waitForTimeout()` 같은 고정 대기는 사용하지 않고, 실패 시 스크린샷·trace·video를 리포트에서 확인합니다.
