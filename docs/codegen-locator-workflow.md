# Locator 검증 기준

locator는 실제 화면을 확인한 뒤 등록합니다. 우선순위는 `getByRole()`, `getByLabel()`, `getByPlaceholder()`, 정확한 텍스트, 검증된 안정 속성입니다. CSS selector는 의미 기반 locator를 쓸 수 없을 때만 사용합니다.

Codegen 결과는 후보로 취급합니다. 위치 기반 selector를 확인 없이 테스트에 넣지 않고, 검증 결과는 `locator-dictionary-template.md`에 기록합니다.
