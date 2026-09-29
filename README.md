# UI Automation Portfolio Sample

Playwright and TypeScript project layout for maintainable UI checks in internal or offline environments. This portfolio version contains no customer URLs, credentials, captured pages, test results, or product-specific locators.

## Layout

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

## Design

- Page objects own stable locators, actions, and page-level assertions.
- Tests express one behavior using Arrange, Act, Assert and keep business flow outside page objects.
- Fixtures share setup and evidence hooks without duplicating test logic.
- Evidence helpers organize screenshots and reports while sensitive runtime output stays ignored.
- Locator documentation records only selectors verified against the intended UI.

## Setup

Use a locally approved Playwright package cache or package mirror in closed environments. Copy `.env.example` to an ignored local `.env` and set an authorized test URL and credentials. No real target values are included here.

```bash
npm install
npx playwright install chromium
npx playwright test
```

This folder is a portfolio structure sample. Specs and locators should be added only after the target interface and expected behavior have been verified.
