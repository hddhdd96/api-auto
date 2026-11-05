#!/usr/bin/env python3
"""접두사 또는 ID 목록 기반 벌크 리소스 삭제 데모.

이력서 포인트: 스모크/배치 실행 후 남은 테스트 리소스를 stub API에 대해
prefix 또는 id-list 기준으로 일괄 정리합니다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from demos._lib.http_client import ApiClient


def ensure_token(client: ApiClient) -> None:
    if client.token:
        return
    user = os.environ.get("DEMO_USERNAME", "qa-demo")
    password = os.environ.get("DEMO_PASSWORD", "demo-pass-1234")
    resp = client.request(
        "POST",
        "/auth/token",
        json_body={"username": user, "password": password},
        auth=False,
    )
    if resp.status != 200:
        raise SystemExit(f"login failed: {resp.status} {resp.body}")
    client.token = resp.body["access_token"]


def list_targets(client: ApiClient, *, prefix: str | None, ids: list[str]) -> list[dict]:
    if ids:
        # ID 목록 모드: 전체 목록에서 교집합
        resp = client.request("GET", "/resources")
        if resp.status != 200:
            raise SystemExit(f"list failed: {resp.status} {resp.body}")
        wanted = set(ids)
        return [r for r in resp.body["items"] if r["id"] in wanted]

    query = {"prefix": prefix} if prefix else None
    resp = client.request("GET", "/resources", query=query)
    if resp.status != 200:
        raise SystemExit(f"list failed: {resp.status} {resp.body}")
    return list(resp.body["items"])


def delete_one(client: ApiClient, resource_id: str) -> dict:
    resp = client.request("DELETE", f"/resources/{resource_id}")
    return {"id": resource_id, "status": resp.status, "body": resp.body}


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk delete demo against stub API")
    parser.add_argument("--prefix", default=None, help="resource name prefix, e.g. qa-smoke-")
    parser.add_argument(
        "--ids",
        default=None,
        help="comma-separated resource IDs (overrides --prefix)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "artifacts" / "bulk_delete_report.json",
    )
    args = parser.parse_args()

    ids = [x.strip() for x in (args.ids or "").split(",") if x.strip()]
    if not ids and not args.prefix:
        parser.error("provide --prefix or --ids")

    client = ApiClient()
    ensure_token(client)
    targets = list_targets(client, prefix=args.prefix, ids=ids)

    results = []
    for item in targets:
        if args.dry_run:
            entry = {"id": item["id"], "name": item["name"], "status": "dry-run"}
            print(f"[dry-run] would delete {item['id']} ({item['name']})")
        else:
            entry = delete_one(client, item["id"])
            entry["name"] = item["name"]
            print(f"[delete] {item['id']} -> HTTP {entry['status']}")
        results.append(entry)

    report = {
        "mode": "ids" if ids else "prefix",
        "selector": ids if ids else args.prefix,
        "dry_run": args.dry_run,
        "matched": len(targets),
        "results": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[report] wrote {args.report} matched={len(targets)}")

    failures = [r for r in results if not args.dry_run and r.get("status") != 200]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
