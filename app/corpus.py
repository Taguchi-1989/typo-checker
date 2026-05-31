"""Corpus（用例コーパス）Store（§9 方式A: 用例 + Few-shot 注入）。

ローカル保存のみ・外部送信なし（§9.3）。重みは変えず、文脈で寄せる。
corpus.json に CorpusItem(§12.3) の配列を保持する。
"""

import json
import os

from app.config import CORPUS_PATH


def _new_id(existing):
    """衝突しない連番ID（c0001 形式）。Date/random は使わず決定的に採番。"""
    n = 1
    used = {it.get("id") for it in existing}
    while f"c{n:04d}" in used:
        n += 1
    return f"c{n:04d}"


class CorpusStore:
    def __init__(self, path=CORPUS_PATH):
        self.path = path
        self.items = self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else data.get("items", [])
        except (OSError, ValueError):
            return []

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)

    def add(self, mode, source_text, accepted_text, created_at, tags=None, max_items=200):
        """採用ペアを1件追加（§9.1 採用フロー）。created_at は呼び出し側で生成して渡す。"""
        item = {
            "id": _new_id(self.items),
            "mode": mode,
            "source_text": source_text or "",
            "accepted_text": accepted_text or "",
            "tags": tags or [],
            "created_at": created_at,
        }
        self.items.append(item)
        self._trim(max_items)
        self._save()
        return item

    def import_bulk(self, mode, blob, created_at, max_items=200):
        """全文貼り付け一括インポート（§9.1 Phase 2）。

        空行区切りの各ブロックを「良い文例」(accepted_text のみ)として取り込む。
        """
        blocks = [b.strip() for b in blob.replace("\r\n", "\n").split("\n\n")]
        added = 0
        for b in blocks:
            if not b:
                continue
            self.items.append({
                "id": _new_id(self.items),
                "mode": mode,
                "source_text": "",
                "accepted_text": b,
                "tags": ["import"],
                "created_at": created_at,
            })
            added += 1
        self._trim(max_items)
        self._save()
        return added

    def delete(self, item_id):
        before = len(self.items)
        self.items = [it for it in self.items if it.get("id") != item_id]
        if len(self.items) != before:
            self._save()
            return True
        return False

    def list(self, mode=None):
        if mode is None:
            return list(self.items)
        return [it for it in self.items if it.get("mode") == mode]

    def select_fewshot(self, mode, n):
        """モード一致の最新 n 件を返す（§9.1 将来は類似度上位）。"""
        if n <= 0:
            return []
        matched = [it for it in self.items if it.get("mode") == mode]
        return matched[-n:]

    def _trim(self, max_items):
        if max_items and len(self.items) > max_items:
            # 古いものから捨てる
            self.items = self.items[-max_items:]
