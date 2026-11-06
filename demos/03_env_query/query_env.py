#!/usr/bin/env python3
"""환경(env) 목록 조회·선택 자동화 데모.

이력서 포인트: stub API에서 환경 목록을 조회하고 tag/status/name 기준으로
테스트 대상 환경을 고릅니다.
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


def pick_env(items: list[dict], *, name: str | None, prefer_ready: bool) -> dict | None:
    if name:
        for item in items:
            if item["name"] == name or item["id"] == name:
                return item
        return None
    if prefer_ready:
        ready = [i for i in items if i.get("status") == "ready"]
        if ready:
            return ready[0]
    return items[0] if items else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Environment query demo")
    parser.add_argument("--tag", default=None, help="filter by tag, e.g. smoke")
    parser.add_argument("--status", default=None, help="filter by status, e.g. ready")
    parser.add_argument("--name", default=None, help="pick by exact name or id")
    parser.add_argument("--prefer-ready", action="store_true", default=True)
    parser.add_argument("--no-prefer-ready", action="store_false", dest="prefer_ready")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "artifacts" / "selected_env.json",
    )
    args = parser.parse_args()

    client = ApiClient()
    ensure_token(client)

    query = {}
    if args.tag:
        query["tag"] = args.tag
    if args.status:
        query["status"] = args.status

    resp = client.request("GET", "/environments", query=query or None)
    if resp.status != 200:
        raise SystemExit(f"list environments failed: {resp.status} {resp.body}")

    items = resp.body["items"]
    selected = pick_env(items, name=args.name, prefer_ready=args.prefer_ready)
    if selected is None:
        print("[env] no environment matched", file=sys.stderr)
        return 1

    payload = {
        "filter": {"tag": args.tag, "status": args.status, "name": args.name},
        "candidates": [{"id": i["id"], "name": i["name"], "status": i["status"]} for i in items],
        "selected": selected,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"[env] candidates={len(items)} selected={selected['name']} ({selected['id']})")
    print(f"[env] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
