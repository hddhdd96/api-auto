# api-auto — QA API 자동화 포트폴리오 데모

로컬 stub API만 사용하는 **공개용** QA 자동화 샘플입니다.  
회사 코드·실계정·실클라우드·고객명은 포함하지 않습니다.

| 이력서 포인트 | 폴더 | 한 줄 요약 |
|---|---|---|
| 토큰 갱신 데몬 | `demos/01_token_refresh/` | JWT `exp` 기반 refresh loop + PID/파일 락 |
| 벌크 리소스 삭제 | `demos/02_bulk_delete/` | prefix 또는 ID 목록으로 stub 리소스 정리 |
| 환경 조회 자동화 | `demos/03_env_query/` | tag/status/name으로 테스트 환경 선택 |
| CSV/Excel 자동 채움 | `demos/04_csv_xlsx/` | 결과 JSON → CSV + 최소 xlsx (stdlib) |

## 요구 사항

- Python 3.9+
- Bash, curl (일괄 실행 스크립트용)
- 외부 pip 패키지 **불필요** (표준 라이브러리만)

## 빠른 실행

```bash
# 1) 회귀 스모크 (stub를 테스트가 직접 기동)
python3 -m unittest discover -s tests -v -f

# 2) 대화형: stub 띄운 뒤 데모 개별 실행
./scripts/run_stub.sh
# 다른 터미널에서:
export BASE_URL=http://127.0.0.1:8765
python3 demos/01_token_refresh/refresh_daemon.py --max-refreshes 2
python3 demos/03_env_query/query_env.py --tag smoke
python3 demos/02_bulk_delete/bulk_delete.py --prefix qa-smoke-
python3 demos/04_csv_xlsx/fill_report.py

# 3) 한 번에
./scripts/run_all_demos.sh
```

산출물은 `artifacts/` 아래에 생성됩니다 (`token_state.json`, `selected_env.json`, `bulk_delete_report.json`, `qa_report.csv`, `qa_report.xlsx`).

## Stub API (가짜)

`stub/server.py`가 `127.0.0.1:8765`에서 동작합니다.

| Method | Path | 설명 |
|---|---|---|
| POST | `/auth/token` | username/password → access + refresh |
| POST | `/auth/refresh` | refresh_token 교체 발급 |
| GET | `/environments` | `?tag=` `?status=` 필터 |
| GET | `/environments/{id\|name}` | 단건 조회 |
| GET | `/resources` | `?prefix=` 이름 접두사 필터 |
| DELETE | `/resources/{id}` | 단건 삭제 |
| POST | `/admin/reset` | 시드 데이터 초기화 (로컬 전용) |
| GET | `/health` | 헬스체크 |

시드 데이터: `stub/fixtures/seed.json`  
데모 계정(가짜): `qa-demo` / `demo-pass-1234` — `.env.example` 참고.

## 이력서 매핑 (상세)

1. **Token refresh daemon** — access TTL이 짧게 설정된 stub에서 만료 직전(`--skew-seconds`) refresh를 반복하고, `fcntl` 파일 락으로 중복 데몬을 거부합니다.
2. **Bulk resource delete** — `qa-smoke-` 같은 테스트 접두사 또는 `--ids` 목록으로 남은 리소스를 일괄 삭제하고 JSON 리포트를 남깁니다.
3. **Environment query** — tag=`smoke` 등으로 후보를 좁힌 뒤 ready 환경을 고르고 `selected_env.json`에 기록합니다.
4. **Light CSV/XLSX** — 위 결과 JSON을 읽어 행을 채웁니다. 무거운 Excel 파이프라인 대신 stdlib `csv` + OOXML zip 최소 구현입니다. 스크린샷 자리표시자: `artifacts/SCREENSHOTS.md`.

## 설정

```bash
cp .env.example .env   # 값은 전부 그대로 두세요 (실클라우드 URL/토큰 금지)
```

## CI

`main` push / PR에서 `python3 -m unittest discover -s tests -v -f` 만 실행합니다.

## 범위 밖 / 의도적 생략

- 회사 org 저장소·내부 호스트·실토큰
- 대용량 Excel 증거 파이프라인
- 실제 클라우드 프로바이더 SDK
