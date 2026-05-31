"""プロンプト組み立て（§8.4）と Corpus（§9）の詳細テスト。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.corpus import CorpusStore  # noqa: E402
from app.jobs import now_iso  # noqa: E402
from app.prompts import DEFAULT_INSTRUCTIONS, build_prompt  # noqa: E402


def test_prompt_basic():
    p = build_prompt("typo", "テスト本文")
    assert DEFAULT_INSTRUCTIONS["typo"].splitlines()[0] in p
    assert p.rstrip().endswith("テスト本文")
    assert "参考例" not in p  # fewshot無し
    print("OK prompt_basic")


def test_prompt_override():
    custom = {"typo": "独自の指示です"}
    p = build_prompt("typo", "本文", instructions=custom)
    assert "独自の指示です" in p
    assert "校正アシスタント" not in p  # 既定が使われていない
    # business は override に無いので既定にフォールバック
    p2 = build_prompt("business", "本文", instructions=custom)
    assert "ビジネス文面補正アシスタント" in p2
    print("OK prompt_override")


def test_prompt_fewshot():
    fs = [
        {"source_text": "雑", "accepted_text": "丁寧"},
        {"source_text": "", "accepted_text": "良い文例のみ"},
        {"source_text": "x", "accepted_text": ""},  # accepted空はスキップ
    ]
    p = build_prompt("business", "本体", fewshot=fs)
    assert "参考例" in p
    assert "入力: 雑" in p and "出力: 丁寧" in p
    assert "良い文例: 良い文例のみ" in p
    assert "入力文:\n本体" in p
    print("OK prompt_fewshot")


def test_corpus_trim(tmp="tests/_tmp_corpus2.json"):
    if os.path.exists(tmp):
        os.remove(tmp)
    store = CorpusStore(path=tmp)
    for i in range(10):
        store.add("typo", f"src{i}", f"acc{i}", now_iso(), max_items=3)
    # max_items=3 で古いものが捨てられる
    items = store.list()
    assert len(items) == 3, len(items)
    assert items[-1]["accepted_text"] == "acc9"
    assert items[0]["accepted_text"] == "acc7", items[0]["accepted_text"]
    # 永続化されているか（再読込）
    store2 = CorpusStore(path=tmp)
    assert len(store2.list()) == 3
    # fewshotはモード一致の最新N件
    store2.add("business", "b", "b", now_iso(), max_items=100)
    fs = store2.select_fewshot("typo", 2)
    assert len(fs) == 2 and all(x["mode"] == "typo" for x in fs)
    assert store2.select_fewshot("typo", 0) == []
    os.remove(tmp)
    print("OK corpus_trim")


def test_corpus_id_unique(tmp="tests/_tmp_corpus3.json"):
    if os.path.exists(tmp):
        os.remove(tmp)
    store = CorpusStore(path=tmp)
    store.add("typo", "a", "a", now_iso())
    store.add("typo", "b", "b", now_iso())
    ids = [it["id"] for it in store.list()]
    assert len(ids) == len(set(ids)), "ID重複"
    # 中間削除後の採番が衝突しない
    store.delete(ids[0])
    store.add("typo", "c", "c", now_iso())
    ids2 = [it["id"] for it in store.list()]
    assert len(ids2) == len(set(ids2)), "削除後にID重複"
    os.remove(tmp)
    print("OK corpus_id_unique")


if __name__ == "__main__":
    test_prompt_basic()
    test_prompt_override()
    test_prompt_fewshot()
    test_corpus_trim()
    test_corpus_id_unique()
    print("\nPROMPTS/CORPUS TESTS PASSED")
