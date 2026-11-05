"""Tiny JSON HTTP client over urllib (no third-party deps)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class Response:
    status: int
    body: Any
    headers: dict[str, str]


class ApiClient:
    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("BASE_URL", "http://127.0.0.1:8765")).rstrip("/")
        self.token = token or os.environ.get("API_TOKEN")

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        query: dict[str, str] | None = None,
        auth: bool = True,
    ) -> Response:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"

        data = None
        headers = {"Accept": "application/json"}
        if json_body is not None:
            data = json.dumps(json_body).encode()
            headers["Content-Type"] = "application/json"
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode() or "{}"
                body = json.loads(raw) if raw.strip() else {}
                return Response(status=resp.status, body=body, headers=dict(resp.headers))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode() or "{}"
            try:
                body = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                body = {"error": raw}
            return Response(status=exc.code, body=body, headers=dict(exc.headers or {}))
