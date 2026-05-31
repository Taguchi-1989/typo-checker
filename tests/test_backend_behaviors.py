"""バックエンドの分岐挙動テスト（§10 エラー処理 / §7.3 コピー挙動 / §18.3 採否）。

偽Ollama + 通知のモック + Tkイベントの手動pumpで、本物のGUI操作なしに
エラーパスと採否ガードを検証する。settings.json を上書きするため、
テスト後に削除して既定へ戻す。
"""
import json
import os
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import clipboard, config  # noqa: E402
from app import notify as notify_mod  # noqa: E402

RESPONSE = "はい、補正後の本文です。"


def start_fake_ollama(port, fail=False):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, code, obj):
            data = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self._json(200, {"models": [{"name": "fake:latest"}]})

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            if fail:
                self._json(500, {"error": "boom"})
            else:
                self._json(200, {"response": RESPONSE})

    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def build_backend(overrides, backend_port, ollama_port):
    settings = json.loads(json.dumps(config.DEFAULT_SETTINGS))
    settings["llm"]["endpoint"] = f"http://127.0.0.1:{ollama_port}"
    settings["llm"]["model"] = "fake:latest"
    settings["llm"]["timeout_sec"] = 5
    settings["server"]["port"] = backend_port
    for path, val in overrides.items():
        cur = settings
        keys = path.split(".")
        for k in keys[:-1]:
            cur = cur[k]
        cur[keys[-1]] = val
    config.save_settings(settings)

    # 通知をモック（toast を出さず記録）
    notes = []
    notify_mod.notify = lambda title, body: notes.append((title, body))

    from app.backend import Backend
    be = Backend()
    be._notes = notes
    return be


def pump(be, seconds):
    end = time.time() + seconds
    while time.time() < end:
        be.root.update()
        time.sleep(0.02)


def submit(port, mode, text):
    body = json.dumps({"mode": mode, "text": text}).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{port}/job", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --- シナリオ ---------------------------------------------------------------
def scenario_max_chars():
    fake = start_fake_ollama(12001)
    be = build_backend({"max_chars": 10}, 8811, 12001)
    try:
        pump(be, 0.2)
        submit(8811, "typo", "あ" * 50)  # 上限超過
        pump(be, 0.5)
        assert not be._result_windows, "超過時に結果ウィンドウが出てはいけない"
        assert be._active_jobs == 0
        titles = [t for t, _ in be._notes]
        assert any("文字数超過" in t for t in titles), be._notes
        print("OK max_chars 拒否")
    finally:
        be._quit(); fake.shutdown()


def scenario_empty():
    fake = start_fake_ollama(12002)
    be = build_backend({}, 8812, 12002)
    try:
        pump(be, 0.2)
        submit(8812, "business", "   \n  ")  # 空白のみ
        pump(be, 0.5)
        assert not be._result_windows
        titles = [t for t, _ in be._notes]
        assert any("取得失敗" in t for t in titles), be._notes
        print("OK 空選択 拒否")
    finally:
        be._quit(); fake.shutdown()


def scenario_llm_failure_and_accept_guard():
    # 到達不能エンドポイント（偽Ollamaを立てない）
    be = build_backend({"corpus.enabled": True}, 8813, 12999)
    sentinel = "SENTINEL-CLIP"
    clipboard.set_clipboard_text(sentinel)
    try:
        pump(be, 0.2)
        submit(8813, "typo", "本文テスト")
        pump(be, 3.0)  # 接続失敗まで待つ
        assert be._result_windows, "失敗でも結果ウィンドウは出す(§10)"
        win = next(iter(be._result_windows.values()))
        assert win.job.status == "failed", win.job.status
        # 失敗時はクリップボードを上書きしない
        assert clipboard.get_clipboard_text() == sentinel, "失敗時にクリップボード上書き"
        # 失敗ジョブを採用Yしてもコーパスに入らない（誤学習防止）
        before = len(be.corpus.list())
        be._on_accept(win.job, True, win.job.result_text)
        assert len(be.corpus.list()) == before, "失敗ジョブがCorpusへ混入"
        print("OK LLM失敗→ウィンドウ表示/クリップボード保護/採用ガード")
    finally:
        be._quit()


def scenario_copy_off():
    fake = start_fake_ollama(12004)
    be = build_backend({"clipboard.copy_result_on_complete": False}, 8814, 12004)
    sentinel = "KEEP-ME"
    clipboard.set_clipboard_text(sentinel)
    try:
        pump(be, 0.2)
        submit(8814, "typo", "誤字テスト")
        pump(be, 2.5)
        win = next(iter(be._result_windows.values()))
        assert win.job.status == "done"
        assert win.job.result_text == "補正後の本文です。", win.job.result_text
        # copy_result_on_complete=False なので自動コピーしない（§7.3 保護モード）
        assert clipboard.get_clipboard_text() == sentinel, "自動コピー無効が効いていない"
        # コピーボタン相当で明示コピー
        be._set_clipboard(win.job.result_text)
        assert clipboard.get_clipboard_text() == "補正後の本文です。"
        print("OK copy_result_on_complete=False 保護→明示コピー")
    finally:
        be._quit(); fake.shutdown()


SCENARIOS = {
    "max_chars": scenario_max_chars,
    "empty": scenario_empty,
    "fail": scenario_llm_failure_and_accept_guard,
    "copy_off": scenario_copy_off,
}


def _run_all_in_subprocesses():
    """各シナリオを別プロセスで実行（Tkインタプリタは1プロセス1個に限定）。"""
    import subprocess

    orig_clip = clipboard.get_clipboard_text() if clipboard._IS_WIN else None
    failed = []
    try:
        for name in SCENARIOS:
            r = subprocess.run([sys.executable, os.path.abspath(__file__), name])
            if r.returncode:
                failed.append(name)
    finally:
        if orig_clip is not None:
            clipboard.set_clipboard_text(orig_clip)
        if os.path.exists(config.SETTINGS_PATH):
            os.remove(config.SETTINGS_PATH)
    if failed:
        print("BACKEND BEHAVIOR FAILED:", ", ".join(failed))
        sys.exit(1)
    print("\nBACKEND BEHAVIOR TESTS PASSED")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 単一シナリオを1プロセスで実行（1 Tk root / process）
        SCENARIOS[sys.argv[1]]()
    else:
        _run_all_in_subprocesses()
