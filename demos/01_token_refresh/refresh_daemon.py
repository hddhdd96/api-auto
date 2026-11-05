#!/usr/bin/env python3
"""JWT exp 기반 토큰 갱신 데몬 (PID/파일 락 데모).

이력서 포인트: access token 만료 전에 refresh loop로 세션을 유지하고,
중복 실행은 PID 파일 락으로 막습니다. 실제 클라우드가 아닌 로컬 stub만 사용합니다.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from demos._lib import jwt_util
from demos._lib.http_client import ApiClient

DEFAULT_LOCK = Path(os.environ.get("TOKEN_DAEMON_LOCK", ROOT / "artifacts" / "token_refresh.lock"))
DEFAULT_STATE = Path(os.environ.get("TOKEN_DAEMON_STATE", ROOT / "artifacts" / "token_state.json"))


class PidFileLock:
    """fcntl 기반 단일 인스턴스 락 + PID 기록."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh = None

    def acquire(self) -> None:
        import fcntl

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+", encoding="utf-8")
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._fh.seek(0)
            other = self._fh.read().strip() or "?"
            raise SystemExit(f"another refresh daemon holds the lock (pid={other})") from exc
        self._fh.seek(0)
        self._fh.truncate()
        self._fh.write(str(os.getpid()))
        self._fh.flush()

    def release(self) -> None:
        if self._fh is None:
            return
        import fcntl

        fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        self._fh.close()
        self._fh = None
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


def login(client: ApiClient) -> dict:
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
    return resp.body


def refresh(client: ApiClient, refresh_token: str) -> dict:
    resp = client.request(
        "POST",
        "/auth/refresh",
        json_body={"refresh_token": refresh_token},
        auth=False,
    )
    if resp.status != 200:
        raise SystemExit(f"refresh failed: {resp.status} {resp.body}")
    return resp.body


def save_state(path: Path, tokens: dict, refresh_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    secret = os.environ.get("JWT_SECRET", "demo-only-secret-not-for-prod")
    access = tokens["access_token"]
    payload = {
        "refresh_count": refresh_count,
        "access_exp": jwt_util.decode(access, secret, verify_exp=False)["exp"],
        "expires_in": tokens.get("expires_in"),
        "updated_at": int(time.time()),
        # 데모용: access/refresh 원문은 저장하지 않고 마스킹만 남김
        "access_token_preview": access[:16] + "...",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_loop(
    *,
    max_refreshes: int,
    skew_seconds: int,
    poll_seconds: float,
    lock_path: Path,
    state_path: Path,
) -> int:
    lock = PidFileLock(lock_path)
    lock.acquire()
    stop = {"flag": False}

    def _stop(_signum, _frame) -> None:
        stop["flag"] = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    client = ApiClient()
    secret = os.environ.get("JWT_SECRET", "demo-only-secret-not-for-prod")
    tokens = login(client)
    client.token = tokens["access_token"]
    refresh_count = 0
    save_state(state_path, tokens, refresh_count)
    print(f"[daemon] started pid={os.getpid()} skew={skew_seconds}s max_refreshes={max_refreshes}")

    try:
        while not stop["flag"]:
            remaining = jwt_util.seconds_until_exp(tokens["access_token"], secret)
            if remaining <= skew_seconds:
                tokens = refresh(client, tokens["refresh_token"])
                client.token = tokens["access_token"]
                refresh_count += 1
                save_state(state_path, tokens, refresh_count)
                print(f"[daemon] refreshed #{refresh_count} expires_in={tokens['expires_in']}s")
                if max_refreshes > 0 and refresh_count >= max_refreshes:
                    print("[daemon] max refreshes reached, exiting cleanly")
                    return 0
            time.sleep(poll_seconds)
    finally:
        lock.release()
        print("[daemon] lock released")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Token refresh daemon demo")
    parser.add_argument("--max-refreshes", type=int, default=2, help="0 = run until signal")
    parser.add_argument("--skew-seconds", type=int, default=3, help="refresh when remaining <= skew")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--lock-file", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()
    return run_loop(
        max_refreshes=args.max_refreshes,
        skew_seconds=args.skew_seconds,
        poll_seconds=args.poll_seconds,
        lock_path=args.lock_file,
        state_path=args.state_file,
    )


if __name__ == "__main__":
    raise SystemExit(main())
