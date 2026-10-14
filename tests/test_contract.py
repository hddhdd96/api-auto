"""The negative fixtures must fail the scenario; they are not xfail/quarantined tests."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("demo_server", ROOT / "demo/server.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LifecycleContractTests(unittest.TestCase):
    def run_scenario(self, mode):
        server = module.DemoServer(("127.0.0.1", 0), mode)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                environment = {
                    **os.environ,
                    "BASE_URL": f"http://127.0.0.1:{server.server_port}",
                    "API_TOKEN": "demo-token", "ENV_FILE": str(Path(directory) / "absent.env"),
                    "LOG_DIR": directory, "INSTANCE_NAME": 'qa-name-"quoted"',
                    "POLL_INTERVAL": "1", "TIMEOUT_VM_ACTIVE": "2", "TIMEOUT_DELETE": "2",
                }
                result = subprocess.run(
                    ["bash", str(ROOT / "scripts/run.sh")], env=environment,
                    capture_output=True, text=True, timeout=15,
                )
                records = list(Path(directory).glob("*.resources.json"))
                self.assertEqual(len(records), 1, result.stdout + result.stderr)
                remaining = json.loads(records[0].read_text())
                return result, remaining, dict(server.resources), server.delete_requests
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_201_create_preserves_status_and_verifies_deletion(self):
        result, remaining, resources, deletes = self.run_scenario("normal")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("total=4 pass=4 fail=0", result.stdout)
        self.assertEqual((remaining, resources, deletes), ([], {}, 1))

    def test_http_200_business_failure_remains_failure_after_cleanup(self):
        result, remaining, resources, deletes = self.run_scenario("business-error")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("business_result", result.stderr)
        self.assertEqual((remaining, resources, deletes), ([], {}, 1))

    def test_terminal_error_does_not_pass(self):
        result, remaining, resources, deletes = self.run_scenario("terminal-error")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("actual=ERROR", result.stderr)
        self.assertEqual((remaining, resources, deletes), ([], {}, 1))

    def test_inactive_does_not_match_active(self):
        result, remaining, resources, deletes = self.run_scenario("inactive")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("actual=INACTIVE", result.stderr)
        self.assertEqual((remaining, resources, deletes), ([], {}, 1))

    def test_wrong_resource_name_fails_and_cleans_up(self):
        result, remaining, resources, deletes = self.run_scenario("wrong-name")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("resource_name", result.stderr)
        self.assertEqual((remaining, resources, deletes), ([], {}, 1))

    def test_failed_delete_retains_id_without_automatic_retry(self):
        result, remaining, resources, deletes = self.run_scenario("delete-error")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(remaining, list(resources))
        self.assertEqual(len(remaining), 1)
        self.assertEqual(deletes, 1)


class TransportContractTests(unittest.TestCase):
    def test_transport_failure_clears_previous_response_and_preserves_exit_code(self):
        script = r'''source "$1/common/request.sh"
apply_auth_headers
HTTP_STATUS=201 HTTP_BODY=stale
status=0
http_request GET 'unsupported-demo-scheme://invalid' || status=$?
[[ "$status" == 2 && "$HTTP_CURL_EXIT" != 0 && "$HTTP_STATUS" != 201 && "$HTTP_BODY" != stale ]]
'''
        result = subprocess.run(["bash", "-c", script, "contract-test", str(ROOT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(failfast=True)
