# 비정상 TC 초안 생성 지시문

입력: `contract/openapi.json` 전체. 다른 자료(서버 코드, 기존 테스트, 실행 결과)는 주지 않는다.

## 지시

You are a QA engineer. From the OpenAPI document only, draft negative and boundary test cases for this API.

- Cover: authentication (missing/invalid token), each required field missing, wrong types, empty and boundary values, malformed bodies, unknown or already-deleted ids, repeated operations, and unknown paths.
- One request per case. Use `setup` when the case needs a resource first (`create`, `create_then_delete`).
- `expected.status`: the status the document implies. If the document does not define the behavior (for example a maximum length), set `expected.status` to `null` and explain in `basis` that a person must decide.
- `basis`: quote or point to the part of the document the expectation comes from.
- Do not assume server internals. Do not include positive happy-path cases except boundary values that should succeed.
- Output JSON only, matching the schema below. Titles in Korean.

## 출력 형식

```json
{
  "drafts": [
    {
      "id": "D01",
      "category": "auth | missing_field | type | boundary | malformed | not_found | state | path",
      "title": "한국어 한 줄",
      "request": {
        "method": "POST | GET | DELETE",
        "path": "/api/v1/instances or /api/v1/instances/{id}",
        "auth": "valid | none | invalid",
        "setup": "none | create | create_then_delete",
        "body": "JSON 값, 원문 문자열(raw), 또는 null"
      },
      "expected": { "status": 400 },
      "basis": "openapi.json의 근거"
    }
  ]
}
```

`request.path`의 `{id}`는 실행 시 setup으로 만든 id 또는 존재하지 않는 임의 id로 바뀐다. `body`가 `{"raw": "..."}`이면 JSON이 아닌 원문 그대로 보낸다.

## 사용 기록

| 날짜 | AI | 입력 | 결과 |
|---|---|---|---|
| 2026-10-27 | Claude Opus 5.5 (Claude Code 대화) | `contract/openapi.json` | `contract/drafts/2026-10-27-claude.json` |
