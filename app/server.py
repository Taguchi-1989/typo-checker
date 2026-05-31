"""ローカル HTTP 受け口。AHK からの POST /job を受けてバックエンドへ渡す。

外部公開しない（既定 127.0.0.1）。stdlib http.server のみ。
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def make_handler(on_job, is_alive=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # noqa: D401 - アクセスログ抑制
            pass

        def _send(self, code, obj):
            data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path.rstrip("/") in ("/health", ""):
                self._send(200, {"ok": True})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path.rstrip("/") != "/job":
                self._send(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                payload = json.loads(raw.decode("utf-8"))
            except (ValueError, OSError) as e:
                self._send(400, {"error": f"bad request: {e}"})
                return

            mode = payload.get("mode")
            text = payload.get("text", "")
            if mode not in ("business", "typo"):
                self._send(400, {"error": "invalid mode"})
                return

            job_id = on_job(
                mode,
                text,
                payload.get("source_app"),
                payload.get("window_title"),
            )
            self._send(200, {"ok": True, "job_id": job_id})

    return Handler


def start_server(host, port, on_job):
    """別スレッドで HTTP サーバを起動し、(server, thread) を返す。"""
    httpd = ThreadingHTTPServer((host, port), make_handler(on_job))
    thread = threading.Thread(target=httpd.serve_forever, name="tc-http", daemon=True)
    thread.start()
    return httpd, thread
