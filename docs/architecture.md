# Architecture

```text
Playwright spec → fixture → flow/test steps → page objects/components → verified UI
                                      └────→ evidence and result utilities
```

| Area | Responsibility |
| --- | --- |
| `tests/scenarios/` | Focused user-visible behavior and business flow |
| `pages/` | Reusable locators, page actions, and page-level assertions |
| `pages/components/` | Shared navigation and UI components |
| `fixtures/` | Shared Playwright setup and lifecycle hooks |
| `utils/` | Evidence, logging, and environment helpers |
| `docs/` | Verified locator notes and test specifications |

Prefer accessible locators (`getByRole`, `getByLabel`, `getByPlaceholder`, then exact text) and Playwright assertions with auto-waiting. Avoid fixed sleeps and guessed selectors. Use traces, screenshots, and videos on failure; keep generated artifacts out of commits and review evidence for sensitive content before sharing.
