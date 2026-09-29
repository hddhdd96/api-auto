# UI 자동화 포트폴리오 샘플

내부망과 폐쇄망 환경에서 유지보수하기 쉬운 Playwright·TypeScript UI 자동화 프로젝트 구조입니다. 고객 URL, 인증 정보, 저장된 화면, 테스트 결과, 제품별 locator는 포함하지 않습니다.

## 폴더 구조

```text
ui-auto/
├── config/
│   └── environments.example.env
├── docs/
│   ├── architecture.md
│   ├── locator-dictionary-template.md
│   └── test-spec-template.md
├── fixtures/
│   └── base-test.ts
├── pages/
│   ├── BasePage.ts
│   └── components/
├── tests/
│   ├── scenarios/
│   └── unit/
├── utils/
│   ├── evidence-recorder.ts
│   └── test-logger.ts
├── .env.example
├── .gitignore
├── package.json
├── playwright.config.ts
└── tsconfig.json
```

## 설계

- 페이지 객체는 검증된 locator, 페이지 동작과 페이지 단위 검증을 담당합니다.
- 테스트는 Arrange, Act, Assert 흐름으로 하나의 동작을 확인하고, 업무 흐름을 페이지 객체에 넣지 않습니다.
- fixture에서 공통 준비 작업과 증적 처리를 공유해 중복을 줄입니다.
- 증적 도구는 스크린샷과 리포트를 정리하며, 민감할 수 있는 실행 결과는 Git에서 제외합니다.
- locator 문서에는 실제 화면에서 확인한 선택자만 기록합니다.

## 실행 준비

폐쇄망에서는 승인된 Playwright 패키지 캐시나 사내 패키지 미러를 사용합니다. `.env.example`을 Git에서 제외되는 로컬 `.env`로 복사해 승인된 테스트 URL과 계정 정보를 설정합니다. 저장소에는 실제 대상 값이 없습니다.

```bash
npm install
npx playwright install chromium
npx playwright test
```

이 폴더는 포트폴리오 구조 예시입니다. 실제 화면과 기대 동작을 확인한 뒤 spec과 locator를 추가하세요.
