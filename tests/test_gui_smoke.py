"""バックエンド全体の煙テスト。

偽 Ollama サーバを立て、settings.json をそれ向きに書き、Backend を構築。
mainloop の代わりに root.update() を回し、HTTP経由でジョブを投入して
「生成→サニタイズ→クリップボード反映→結果ウィンドウ生成」まで通るか確認する。
GUI(tkinter) が必要なので Windows デスクトップ上で実行すること。
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import config  # noqa: E402

FAKE_OLLAMA_PORT = 11999
BACKEND_PORT = 8798
RESPONSE = "はい、修正しました：これは補正後の文です。"


def start_fake_ollama():
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj):
            data = json.dumps(obj).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self._json({"models": [{"name": "fake:latest"}]})

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            self._json({"response": RESPONSE})

    httpd = ThreadingHTTPServer(("127.0.0.1", FAKE_OLLAMA_PORT), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main():
    fake = start_fake_ollama()

    # 偽Ollama向けの設定を書く
    settings = json.loads(json.dumps(config.DEFAULT_SETTINGS))
    settings["llm"]["endpoint"] = f"http://127.0.0.1:{FAKE_OLLAMA_PORT}"
    settings["llm"]["model"] = "fake:latest"
    settings["server"]["port"] = BACKEND_PORT
    config.save_settings(settings)

    from app.backend import Backend
    be = Backend()

    def pump(seconds):
        end = time.time() + seconds
        while time.time() < end:
            be.root.update()
            time.sleep(0.02)

    pump(0.3)

    # HTTP経由でジョブ投入（AHKの代役）
    body = json.dumps({"mode": "typo", "text": "誤字あるテスト文",
                       "window_title": "Notepad"}).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{BACKEND_PORT}/job", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    assert out["ok"], out

    # 生成完了を待つ（ワーカースレッド→キュー→Tkポーリング）
    pump(2.5)

    # 検証: 結果ウィンドウが生成され、サニタイズ済み結果がクリップボードに入っている
    assert be._result_windows, "結果ウィンドウが生成されていない"
    job = next(iter(be._result_windows))
    win = be._result_windows[job]
    result = win.job.result_text
    print("result_text =", repr(result))
    assert result == "これは補正後の文です。", f"サニタイズ結果が不正: {result!r}"
    assert win.job.sanitized is True

    from app import clipboard
    clip = clipboard.get_clipboard_text()
    print("clipboard   =", repr(clip))
    assert clip == "これは補正後の文です。", f"クリップボード不一致: {clip!r}"

    # 採否記録（§18.3）
    be._on_accept(win.job, True, result)
    assert win.job.accepted is True

    be._quit()
    fake.shutdown()
    print("\nGUI SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
