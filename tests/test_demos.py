#!/usr/bin/env python3
"""Smoke tests for the four resume demos against an in-process stub server."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class DemoSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.port = _free_port()
        cls.base = f"http://127.0.0.1:{cls.port}"
        env = os.environ.copy()
        env.update(
            {
                "JWT_SECRET": "demo-only-secret-not-for-prod",
                "ACCESS_TOKEN_TTL": "5",
                "REFRESH_TOKEN_TTL": "60",
                "DEMO_USERNAME": "qa-demo",
                "DEMO_PASSWORD": "demo-pass-1234",
                "BASE_URL": cls.base,
            }
        )
        cls.env = env
        cls.proc = subprocess.Popen(
            [sys.executable, str(ROOT / "stub" / "server.py"), "--host", "127.0.0.1", "--port", str(cls.port)],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"{cls.base}/health", timeout=0.3)
                break
            except Exception:
                if cls.proc.poll() is not None:
                    out, err = cls.proc.communicate(timeout=1)
                    raise RuntimeError(f"stub exited early\nstdout={out}\nstderr={err}")
                time.sleep(0.05)
        else:
            cls.proc.kill()
            raise RuntimeError("stub did not become healthy")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            cls.proc.kill()

    def _reset(self) -> None:
        req = urllib.request.Request(
            f"{self.base}/admin/reset",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3).read()

    def test_token_refresh_daemon(self) -> None:
        self._reset()
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "lock"
            state = Path(tmp) / "state.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "demos/01_token_refresh/refresh_daemon.py"),
                    "--max-refreshes",
                    "1",
                    "--skew-seconds",
                    "4",
                    "--poll-seconds",
                    "0.3",
                    "--lock-file",
                    str(lock),
                    "--state-file",
                    str(state),
                ],
                cwd=str(ROOT),
                env=self.env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            payload = json.loads(state.read_text(encoding="utf-8"))
            self.assertGreaterEqual(payload["refresh_count"], 1)

    def test_env_query_and_bulk_delete_and_report(self) -> None:
        self._reset()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_out = tmp_path / "env.json"
            delete_out = tmp_path / "delete.json"
            csv_out = tmp_path / "report.csv"
            xlsx_out = tmp_path / "report.xlsx"

            env_run = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "demos/03_env_query/query_env.py"),
                    "--tag",
                    "smoke",
                    "--out",
                    str(env_out),
                ],
                cwd=str(ROOT),
                env=self.env,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(env_run.returncode, 0, env_run.stdout + env_run.stderr)
            selected = json.loads(env_out.read_text(encoding="utf-8"))["selected"]
            self.assertEqual(selected["name"], "demo-dev")

            delete_run = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "demos/02_bulk_delete/bulk_delete.py"),
                    "--prefix",
                    "qa-smoke-",
                    "--report",
                    str(delete_out),
                ],
                cwd=str(ROOT),
                env=self.env,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(delete_run.returncode, 0, delete_run.stdout + delete_run.stderr)
            report = json.loads(delete_out.read_text(encoding="utf-8"))
            self.assertEqual(report["matched"], 2)

            fill_run = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "demos/04_csv_xlsx/fill_report.py"),
                    "--env-report",
                    str(env_out),
                    "--delete-report",
                    str(delete_out),
                    "--csv-out",
                    str(csv_out),
                    "--xlsx-out",
                    str(xlsx_out),
                ],
                cwd=str(ROOT),
                env=self.env,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(fill_run.returncode, 0, fill_run.stdout + fill_run.stderr)
            self.assertTrue(csv_out.exists())
            self.assertTrue(xlsx_out.exists())
            self.assertGreater(xlsx_out.stat().st_size, 100)

    def test_bulk_delete_by_ids(self) -> None:
        self._reset()
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "ids.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "demos/02_bulk_delete/bulk_delete.py"),
                    "--ids",
                    "res-tmp-001",
                    "--report",
                    str(report),
                ],
                cwd=str(ROOT),
                env=self.env,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["matched"], 1)
            self.assertEqual(payload["results"][0]["status"], 200)


if __name__ == "__main__":
    unittest.main()
