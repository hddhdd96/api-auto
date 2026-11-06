#!/usr/bin/env python3
"""Local stub API for QA resume demos. Fake values only — no real cloud."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demos._lib import jwt_util  # noqa: E402

SEED_PATH = Path(__file__).resolve().parent / "fixtures" / "seed.json"
DEMO_SECRET = os.environ.get("JWT_SECRET", "demo-only-secret-not-for-prod")
ACCESS_TTL = int(os.environ.get("ACCESS_TOKEN_TTL", "8"))
REFRESH_TTL = int(os.environ.get("REFRESH_TOKEN_TTL", "120"))
DEMO_USER = os.environ.get("DEMO_USERNAME", "qa-demo")
DEMO_PASS = os.environ.get("DEMO_PASSWORD", "demo-pass-1234")


class Store:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.reset()

    def reset(self) -> None:
        with self.lock:
            seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
            self.environments = copy.deepcopy(seed["environments"])
            self.resources = {r["id"]: copy.deepcopy(r) for r in seed["resources"]}
            self.refresh_tokens: set[str] = set()


STORE = Store()


def issue_tokens(sub: str) -> dict[str, Any]:
    now = int(time.time())
    access = jwt_util.encode(
        {"sub": sub, "typ": "access", "iat": now, "exp": now + ACCESS_TTL},
        DEMO_SECRET,
    )
    refresh = jwt_util.encode(
        {"sub": sub, "typ": "refresh", "jti": str(uuid.uuid4()), "iat": now, "exp": now + REFRESH_TTL},
        DEMO_SECRET,
    )
    with STORE.lock:
        STORE.refresh_tokens.add(refresh)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "Bearer",
        "expires_in": ACCESS_TTL,
    }


def require_access(handler: "Handler") -> dict[str, Any] | None:
    auth = handler.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        handler.send_json(401, {"error": "missing_bearer"})
        return None
    token = auth[7:].strip()
    try:
        payload = jwt_util.decode(token, DEMO_SECRET)
    except ValueError as exc:
        handler.send_json(401, {"error": str(exc)})
        return None
    if payload.get("typ") != "access":
        handler.send_json(401, {"error": "not_access_token"})
        return None
    return payload


class Handler(BaseHTTPRequestHandler):
    server_version = "QaDemoStub/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"[stub] {self.address_string()} {fmt % args}\n")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode())

    def send_json(self, status: int, body: Any) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/health":
            self.send_json(200, {"status": "ok"})
            return

        if path == "/environments":
            if require_access(self) is None:
                return
            qs = parse_qs(parsed.query)
            items = list(STORE.environments)
            tag = (qs.get("tag") or [None])[0]
            status = (qs.get("status") or [None])[0]
            if tag:
                items = [e for e in items if tag in e.get("tags", [])]
            if status:
                items = [e for e in items if e.get("status") == status]
            self.send_json(200, {"items": items, "count": len(items)})
            return

        if path.startswith("/environments/"):
            if require_access(self) is None:
                return
            env_id = path.split("/", 2)[2]
            for env in STORE.environments:
                if env["id"] == env_id or env["name"] == env_id:
                    self.send_json(200, env)
                    return
            self.send_json(404, {"error": "environment_not_found"})
            return

        if path == "/resources":
            if require_access(self) is None:
                return
            qs = parse_qs(parsed.query)
            prefix = (qs.get("prefix") or [None])[0]
            items = list(STORE.resources.values())
            if prefix:
                items = [r for r in items if r["name"].startswith(prefix)]
            self.send_json(200, {"items": items, "count": len(items)})
            return

        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        body = self._read_json()

        if path == "/auth/token":
            user = body.get("username")
            password = body.get("password")
            if user != DEMO_USER or password != DEMO_PASS:
                self.send_json(401, {"error": "invalid_credentials"})
                return
            self.send_json(200, issue_tokens(user))
            return

        if path == "/auth/refresh":
            refresh = body.get("refresh_token")
            if not refresh:
                self.send_json(400, {"error": "refresh_token_required"})
                return
            with STORE.lock:
                if refresh not in STORE.refresh_tokens:
                    self.send_json(401, {"error": "unknown_refresh_token"})
                    return
                try:
                    payload = jwt_util.decode(refresh, DEMO_SECRET)
                except ValueError as exc:
                    STORE.refresh_tokens.discard(refresh)
                    self.send_json(401, {"error": str(exc)})
                    return
                if payload.get("typ") != "refresh":
                    self.send_json(401, {"error": "not_refresh_token"})
                    return
                STORE.refresh_tokens.discard(refresh)
            self.send_json(200, issue_tokens(payload["sub"]))
            return

        if path == "/admin/reset":
            # Local demo helper only — not a real cloud admin API.
            STORE.reset()
            self.send_json(200, {"status": "reset"})
            return

        self.send_json(404, {"error": "not_found"})

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if require_access(self) is None:
            return

        if path.startswith("/resources/"):
            res_id = path.split("/", 2)[2]
            with STORE.lock:
                if res_id not in STORE.resources:
                    self.send_json(404, {"error": "resource_not_found"})
                    return
                deleted = STORE.resources.pop(res_id)
            self.send_json(200, {"deleted": deleted})
            return

        self.send_json(404, {"error": "not_found"})


def main() -> int:
    parser = argparse.ArgumentParser(description="QA demo stub API")
    parser.add_argument("--host", default=os.environ.get("STUB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("STUB_PORT", "8765")))
    args = parser.parse_args()

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"stub listening on http://{args.host}:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstub stopped", flush=True)
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
