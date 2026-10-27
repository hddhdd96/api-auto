"""가드레일 재현 테스트.

각 사례는 이 저장소의 실제 파일에 "AI가 실패를 통과시키려고 할 법한 수정"을 적용한 diff를 만들고,
가드레일이 해당 규칙으로 잡는지 확인한다. 원본 문자열이 사라지면 테스트가 실패하므로
예시가 실제 코드와 어긋난 채 남지 않는다.

실행: python3 -m unittest discover -s guardrail -v
"""
import difflib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_test_weakening as guard  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCOPE = guard.load_scope(ROOT / "guardrail" / "scope.txt")


def mutate(path: str, before: str, after: str) -> str:
    """저장소 파일의 before를 after로 바꾼 git 형식 unified diff(-U0)를 만든다."""
    original = (ROOT / path).read_text(encoding="utf-8")
    assert before in original, f"{path}에 예시 원본이 없습니다: {before!r}"
    changed = original.replace(before, after, 1)
    lines = difflib.unified_diff(original.splitlines(), changed.splitlines(),
                                 f"a/{path}", f"b/{path}", n=0, lineterm="")
    return f"diff --git a/{path} b/{path}\n" + "\n".join(lines) + "\n"


def rules(diff: str) -> set[str]:
    return {finding.rule for finding in guard.check_diff(diff, SCOPE)}


class CatchesWeakening(unittest.TestCase):
    def test_active_poll_becomes_glob_match(self):
        # *"$expected"* 는 INACTIVE도 ACTIVE로 인정한다.
        diff = mutate("common/polling.sh", 'if [[ "$status" == "$expected" ]]; then return 0; fi',
                      'if [[ "$status" == *"$expected"* ]]; then return 0; fi')
        self.assertIn("TW05", rules(diff))

    def test_jq_field_assertion_becomes_partial(self):
        diff = mutate("common/assertion.sh", '  if [[ "$actual" != "$expected" ]]; then\n    log_fail "$step" "jq',
                      '  if [[ "$actual" != *"$expected"* ]]; then\n    log_fail "$step" "jq')
        self.assertIn("TW05", rules(diff))

    def test_accepted_http_status_widened(self):
        diff = mutate("scenarios/compute/create_and_delete_instance.sh",
                      '[[ "$HTTP_STATUS" == 200 || "$HTTP_STATUS" == 201 ]]',
                      '[[ "$HTTP_STATUS" == 200 || "$HTTP_STATUS" == 201 || "$HTTP_STATUS" == 202 ]]')
        self.assertIn("TW09", rules(diff))

    def test_final_status_failure_swallowed(self):
        diff = mutate("scenarios/compute/create_and_delete_instance.sh",
                      "ACTIVE \"$HTTP_BODY\" status_active\n", "ACTIVE \"$HTTP_BODY\" status_active || true\n")
        self.assertIn("TW07", rules(diff))

    def test_name_assertion_removed(self):
        diff = mutate("scenarios/compute/create_and_delete_instance.sh",
                      "  assert_jq_equals '.name // .data.name' \"$INSTANCE_NAME\" \"$HTTP_BODY\" resource_name || return 1\n", "")
        self.assertIn("TW01", rules(diff))

    def test_failed_http_assertion_returns_success(self):
        diff = mutate("common/assertion.sh", "    return 1\n  fi\n  return 0\n}\n\nassert_jq_equals",
                      "    return 0\n  fi\n  return 0\n}\n\nassert_jq_equals")
        self.assertTrue({"TW01", "TW06"} & rules(diff))

    def test_delete_retry_introduced(self):
        diff = mutate("config/env.sh", ': "${TIMEOUT_DELETE:=120}"\n',
                      ': "${TIMEOUT_DELETE:=120}"\n: "${DELETE_RETRY:=3}"\n')
        self.assertIn("TW04", rules(diff))

    def test_exact_delete_count_relaxed(self):
        diff = mutate("tests/test_contract.py", "        self.assertEqual(deletes, 1)\n",
                      "        self.assertGreaterEqual(deletes, 1)\n")
        self.assertIn("TW05", rules(diff))

    def test_negative_contract_marked_expected_failure(self):
        diff = mutate("tests/test_contract.py", "    def test_inactive_does_not_match_active(self):",
                      "    @unittest.expectedFailure\n    def test_inactive_does_not_match_active(self):")
        self.assertIn("TW03", rules(diff))

    def test_contract_test_deleted(self):
        source = (ROOT / "tests/test_contract.py").read_text(encoding="utf-8")
        start = source.index("    def test_wrong_resource_name_fails_and_cleans_up")
        end = source.index("    def test_failed_delete_retains_id")
        diff = mutate("tests/test_contract.py", source[start:end], "")
        self.assertIn("TW02", rules(diff))

    def test_guardrail_rule_removed(self):
        diff = mutate("guardrail/scope.txt", "common/*\n", "")
        self.assertIn("TW11", rules(diff))


class AllowsOrdinaryChanges(unittest.TestCase):
    def test_new_assertion_is_not_flagged(self):
        diff = mutate("scenarios/compute/create_and_delete_instance.sh",
                      "  assert_business_success \"$HTTP_BODY\" || return 1\n  assert_jq_equals '.id",
                      "  assert_business_success \"$HTTP_BODY\" || return 1\n"
                      "  assert_jq_equals '.network // .data.network' \"$NETWORK_NAME\" \"$HTTP_BODY\" resource_network || return 1\n"
                      "  assert_jq_equals '.id")
        self.assertEqual(rules(diff), set())

    def test_failure_message_reworded_is_not_flagged(self):
        diff = mutate("common/polling.sh", 'log_fail poll "제한 시간 초과: actual=$status',
                      'log_fail poll "상태 확인 제한 시간 초과: actual=$status')
        self.assertEqual(rules(diff), set())

    def test_glob_to_exact_strengthening_is_not_flagged(self):
        weak = mutate("common/polling.sh", 'if [[ "$status" == "$expected" ]]; then return 0; fi',
                      'if [[ "$status" == *"$expected"* ]]; then return 0; fi')
        restore = "\n".join(
            {"-": "+", "+": "-"}[line[0]] + line[1:]
            if line.startswith(("-", "+")) and not line.startswith(("---", "+++")) else line
            for line in weak.splitlines())
        self.assertEqual(rules(restore), set())

    def test_rule_text_in_guardrail_sources_and_comments_is_not_flagged(self):
        diff = (
            "diff --git a/guardrail/test_check_test_weakening.py b/guardrail/test_check_test_weakening.py\n"
            "--- a/guardrail/test_check_test_weakening.py\n+++ b/guardrail/test_check_test_weakening.py\n"
            "@@ -1,0 +2 @@\n+mutate('playwright.config.ts', 'retries: 0,', 'retries: 2,')  # test.skip(\n"
            "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n"
            "--- a/.github/workflows/ci.yml\n+++ b/.github/workflows/ci.yml\n"
            "@@ -1,0 +2 @@\n+      # retries: 0, 실패를 재시도로 가리지 않는다.\n")
        self.assertEqual(rules(diff), set())

    def test_out_of_scope_file_is_ignored(self):
        diff = mutate("README.md", "`ACTIVE` 완전 일치만 성공입니다", "`ACTIVE` 포함 시 성공입니다")
        self.assertEqual(rules(diff), set())


class CommandLine(unittest.TestCase):
    def run_cli(self, diff: str, *extra: str) -> subprocess.CompletedProcess:
        with tempfile.NamedTemporaryFile("w", suffix=".diff", delete=False, encoding="utf-8") as handle:
            handle.write(diff)
        try:
            environment = {key: value for key, value in os.environ.items()
                           if key not in {"GITHUB_ACTIONS", "GITHUB_STEP_SUMMARY"}}
            return subprocess.run([sys.executable, str(ROOT / "guardrail/check_test_weakening.py"), handle.name, *extra],
                                  capture_output=True, text=True, env=environment)
        finally:
            os.unlink(handle.name)

    def test_weakening_fails_the_job_until_a_person_approves(self):
        diff = mutate("common/polling.sh", 'if [[ "$status" == "$expected" ]]; then return 0; fi',
                      'if [[ "$status" == *"$expected"* ]]; then return 0; fi')
        blocked = self.run_cli(diff)
        self.assertEqual(blocked.returncode, 1, blocked.stdout + blocked.stderr)
        self.assertIn("TW05", blocked.stdout)
        approved = self.run_cli(diff, "--approved")
        self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
        self.assertIn("[WARNING] TW05", approved.stdout)

    def test_bundled_example_is_caught(self):
        example = (ROOT / "guardrail/examples/weaken-active-check.diff").read_text(encoding="utf-8")
        result = self.run_cli(example)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("TW05", result.stdout)


if __name__ == "__main__":
    unittest.main()
