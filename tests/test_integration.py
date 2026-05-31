"""HTTPサーバ + ジョブ投入 + Corpus の結合テスト（Ollama/AHK/GUI不要）。

llm.generate をモックし、tkinter を使わずにバックエンドのコアフローを検証する。
"""
import json
import os
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import llm  # noqa: E402
from app.corpus import CorpusStore  # noqa: E402
from app.jobs import Job, now_iso  # noqa: E402
from app.prompts import build_prompt  # noqa: E402
from app.server import start_server  # noqa: E402


def test_http_job_roundtrip():
    received = []

    def on_job(mode, text, app, title):
        job = Job(mode, text, source_app=app, window_title=title)
        received.append(job)
        return job.job_id

    httpd, _ = start_server("127.0.0.1", 8799, on_job)
    try:
        body = json.dumps({"mode": "typo", "text": "誤字あるテスト",
                           "window_title": "Notepad"}).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:8799/job", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        assert out["ok"] and out["job_id"], out
        assert received and received[0].original_text == "誤字あるテスト"
        assert received[0].window_title == "Notepad"

        # 不正modeは400
        bad = json.dumps({"mode": "x", "text": "a"}).encode("utf-8")
        try:
            urllib.request.urlopen(urllib.request.Request(
                "http://127.0.0.1:8799/job", data=bad,
                headers={"Content-Type": "application/json"}), timeout=3)
            assert False, "should have raised"
        except urllib.error.HTTPError as e:
            assert e.code == 400
        print("OK http_job_roundtrip")
    finally:
        httpd.shutdown()


def test_corpus_cycle(tmp="tests/_tmp_corpus.json"):
    if os.path.exists(tmp):
        os.remove(tmp)
    store = CorpusStore(path=tmp)
    store.add("business", "雑な依頼", "丁寧な依頼です。", now_iso(), max_items=200)
    n = store.import_bulk("typo", "例文A\n\n例文B\n\n例文C", now_iso())
    assert n == 3, n
    fs = store.select_fewshot("typo", 2)
    assert len(fs) == 2
    # few-shot がプロンプトに入る
    p = build_prompt("typo", "本体テキスト", fewshot=fs)
    assert "参考例" in p and "本体テキスト" in p
    # 削除
    first_id = store.list()[0]["id"]
    assert store.delete(first_id)
    assert all(it["id"] != first_id for it in store.list())
    os.remove(tmp)
    print("OK corpus_cycle")


def test_llm_connection_error():
    # 到達不能ポートへ → connection 種別の LLMError
    try:
        llm.generate("http://127.0.0.1:1", "m", "p", 0.2, timeout=2)
        assert False
    except llm.LLMError as e:
        assert e.kind == "connection", e.kind
    print("OK llm_connection_error")


if __name__ == "__main__":
    test_http_job_roundtrip()
    test_corpus_cycle()
    test_llm_connection_error()
    print("\nALL INTEGRATION TESTS PASSED")
