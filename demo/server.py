"""Local synthetic API contract. No cloud connection or third-party dependency."""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4


class DemoServer(ThreadingHTTPServer):
    def __init__(self, address, mode="normal"):
        super().__init__(address, Handler)
        self.mode = mode
        self.resources = {}
        self.delete_requests = 0
        self.lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send_json(self, code, body):
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def authorized(self):
        if self.headers.get("Authorization") == "Bearer demo-token":
            return True
        self.send_json(401, {"returnCode": "UNAUTHORIZED"})
        return False

    def do_POST(self):
        if not self.authorized():
            return
        if self.path != "/api/v1/instances":
            self.send_json(404, {})
            return
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            name = payload["name"]
            if not isinstance(name, str) or not name:
                raise ValueError("name required")
            # README 계약의 필수 항목. 빈 문자열 허용 여부는 요구사항 미정이라 검사하지 않는다(contract 리뷰 D21).
            for field in ("network", "flavor", "image"):
                if not isinstance(payload[field], str):
                    raise ValueError(f"{field} must be a string")
        except (ValueError, KeyError, TypeError):
            self.send_json(400, {"returnCode": "INVALID_INPUT"})
            return
        resource = {"id": str(uuid4()), "name": name, "status": "ACTIVE"}
        with self.server.lock:
            self.server.resources[resource["id"]] = resource
        response = dict(resource, returnCode="COMMON_OK")
        if self.server.mode == "business-error":
            response["returnCode"] = "CREATE_FAILED"
        self.send_json(200 if self.server.mode == "business-error" else 201, response)

    def do_GET(self):
        if not self.authorized():
            return
        resource_id = self.path.removeprefix("/api/v1/instances/")
        with self.server.lock:
            resource = self.server.resources.get(resource_id)
        if resource is None:
            self.send_json(404, {})
            return
        response = dict(resource)
        if self.server.mode == "terminal-error":
            response["status"] = "ERROR"
        elif self.server.mode == "wrong-name":
            response["name"] = "another-instance"
        elif self.server.mode == "inactive":
            response["status"] = "INACTIVE"
        self.send_json(200, response)

    def do_DELETE(self):
        if not self.authorized():
            return
        resource_id = self.path.removeprefix("/api/v1/instances/")
        with self.server.lock:
            self.server.delete_requests += 1
            if self.server.mode == "delete-error":
                self.send_json(500, {"returnCode": "DELETE_FAILED"})
                return
            removed = self.server.resources.pop(resource_id, None)
        self.send_json(200 if removed else 404, {})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    server = DemoServer(("127.0.0.1", args.port))
    print(f"Synthetic API: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
