"""비정상 TC 초안을 로컬 합성 서버에 한 번씩 보내 실제 응답을 기록한다(검토용).

사용: python3 contract/check_drafts.py contract/drafts/2026-10-27-claude.json
결과: 같은 경로에 .results.json을 쓰고 표를 출력한다. 표준 라이브러리만 사용한다.
초안을 바로 회귀 테스트로 쓰지 않는다. 사람이 이 결과를 보고 채택할 초안을 고른다.
"""
import http.client
import importlib.util
import json
from pathlib import Path
import sys
import threading
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("demo_server", ROOT / "demo/server.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)

VALID_BODY = {"name": "qa-draft-setup", "network": "qa-net", "flavor": "qa.small", "image": "qa-base-image"}
TOKENS = {"valid": "Bearer demo-token", "invalid": "Bearer wrong-token", "none": None}


def call(port, method, path, auth="valid", body=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Accept": "application/json"}
    if TOKENS[auth]:
        headers["Authorization"] = TOKENS[auth]
    payload = None
    if isinstance(body, dict) and set(body) == {"raw"}:
        payload = body["raw"].encode()
    elif body is not None:
        payload = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    connection.request(method, path, body=payload, headers=headers)
    response = connection.getresponse()
    text = response.read().decode(errors="replace")
    connection.close()
    return response.status, text


def expand(value):
    if isinstance(value, str) and value.startswith("__REPEAT_"):
        _, char, count = value.strip("_").split("_")
        return char * int(count)
    if isinstance(value, dict):
        return {key: expand(item) for key, item in value.items()}
    if isinstance(value, list):
        return [expand(item) for item in value]
    return value


def run_draft(port, server, draft):
    request = draft["request"]
    resource_id = str(uuid4())
    if request["setup"] in ("create", "create_then_delete"):
        status, text = call(port, "POST", "/api/v1/instances", body=VALID_BODY)
        assert status == 201, f"setup create failed: {status} {text}"
        resource_id = json.loads(text)["id"]
        if request["setup"] == "create_then_delete":
            status, _ = call(port, "DELETE", f"/api/v1/instances/{resource_id}")
            assert status // 100 == 2, f"setup delete failed: {status}"
    path = request["path"].replace("{id}", resource_id)
    status, text = call(port, request["method"], path, request["auth"], expand(request["body"]))
    note = ""
    if draft["request"]["method"] == "DELETE" and request["auth"] != "valid" and request["setup"] == "create":
        note = "삭제되지 않음" if resource_id in server.resources else "인증 없이 삭제됨"
    if request["method"] == "POST" and status == 201:
        note = (note + " " if note else "") + "리소스가 생성됨"
    expected = draft["expected"]["status"]
    allowed = expected if isinstance(expected, list) else [expected]
    verdict = "명세 기대값 없음" if expected is None else ("일치" if status in allowed else "불일치")
    return {"id": draft["id"], "expected": expected, "actual": status, "verdict": verdict, "note": note, "body": text[:120]}


def main(path):
    drafts = json.loads(Path(path).read_text(encoding="utf-8"))["drafts"]
    server = demo.DemoServer(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        results = [run_draft(server.server_port, server, draft) for draft in drafts]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    target = Path(path).with_suffix(".results.json")
    target.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    titles = {draft["id"]: draft["title"] for draft in drafts}
    print("| 초안 | 내용 | 명세상 기대 | 실제 | 비교 | 참고 |\n|---|---|---|---|---|---|")
    for result in results:
        print(f"| {result['id']} | {titles[result['id']]} | {result['expected']} | {result['actual']} | {result['verdict']} | {result['note']} |")
    return results


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "contract/drafts/2026-10-27-claude.json"))
