"""API 계약 기반 비정상 요청 회귀 테스트.

AI가 contract/openapi.json만 보고 만든 초안(contract/drafts/*.json) 중
사람이 검토해 채택한 것(*.review.json의 decision == adopted)만 실행한다.
응답 코드뿐 아니라 거절된 요청이 서버 상태를 바꾸지 않았는지도 확인한다.
"""
import importlib.util
import json
from pathlib import Path
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "contract/drafts/2026-10-27-claude.json"
REVIEW = ROOT / "contract/drafts/2026-10-27-claude.review.json"

runner_spec = importlib.util.spec_from_file_location("check_drafts", ROOT / "contract/check_drafts.py")
runner = importlib.util.module_from_spec(runner_spec)
runner_spec.loader.exec_module(runner)


def adopted_drafts():
    drafts = {draft["id"]: draft for draft in json.loads(DRAFTS.read_text(encoding="utf-8"))["drafts"]}
    review = json.loads(REVIEW.read_text(encoding="utf-8"))["review"]
    return [drafts[item["id"]] for item in review if item["decision"] == "adopted"]


class NegativeContractTests(unittest.TestCase):
    def setUp(self):
        self.server = runner.demo.DemoServer(("127.0.0.1", 0))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_review_keeps_every_draft_accounted_for(self):
        drafts = json.loads(DRAFTS.read_text(encoding="utf-8"))["drafts"]
        review = json.loads(REVIEW.read_text(encoding="utf-8"))
        self.assertEqual([item["id"] for item in review["review"]], [draft["id"] for draft in drafts])
        self.assertTrue(all(item["decision"] in ("adopted", "excluded") and item["reason"] for item in review["review"]))
        for item in review["review"]:
            if item["decision"] == "adopted":
                draft = next(draft for draft in drafts if draft["id"] == item["id"])
                self.assertIsNotNone(draft["expected"]["status"], f"{item['id']}: 기대값 없는 초안은 채택할 수 없다")

    def test_adopted_drafts_match_the_contract(self):
        for draft in adopted_drafts():
            with self.subTest(draft=draft["id"], title=draft["title"]):
                before = dict(self.server.resources)
                result = runner.run_draft(self.server.server_port, self.server, draft)
                expected = draft["expected"]["status"]
                allowed = expected if isinstance(expected, list) else [expected]
                self.assertIn(result["actual"], allowed, f"{draft['id']} {draft['title']}: {result['body']}")
                request = draft["request"]
                if request["method"] == "POST" and result["actual"] >= 400:
                    self.assertEqual(self.server.resources, before, f"{draft['id']}: 거절된 생성 요청이 리소스를 남김")
                if request["method"] == "DELETE" and request["auth"] != "valid":
                    self.assertEqual(result["note"], "삭제되지 않음", f"{draft['id']}: 인증 없이 삭제됨")


if __name__ == "__main__":
    unittest.main()
