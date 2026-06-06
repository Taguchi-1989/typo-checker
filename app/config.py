"""設定の保持・編集（§12.2 Settings）。

プロジェクトルートの settings.json に保存。存在しなければ既定値を書き出す。
読み込み時は既定値とディープマージし、新フィールド追加に追従する。
"""

import copy
import json
import os

# プロジェクトルート = app/ の親
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(ROOT_DIR, "settings.json")
CORPUS_PATH = os.path.join(ROOT_DIR, "corpus.json")

# §8.2 RTX 3060 / 6GB 向けモデル候補（先頭ほど推奨）。
# 6GBに完全収載できる4B以下が基本。8B級(qwen3:8b 4.9GB等)はKVキャッシュ込みで
# 6GBを超え一部CPUオフロード→生成(予測変換)が遅くなるため非採用。
MODEL_CANDIDATES = [
    # dahara1 日本語特化 Qwen3.5-4B(Q6_K, ~3.8GB)。think=false で warm 約1秒・補正力◎。
    # 作成は models/qwen3.5-jp-4b.Modelfile を使う（RENDERER/PARSER qwen3.5 が必須。
    # HF直 pull/cp だけだと思考が停止せず1補正57秒になる。理由はModelfile冒頭参照）:
    #   ollama pull hf.co/dahara1/Qwen3.5-4B-UD-japanese-imatrix:Q6_K
    #   ollama create qwen3.5-jp-4b:q6 -f models/qwen3.5-jp-4b.Modelfile
    "qwen3.5-jp-4b:q6",
    "qwen3.5:4b",                  # 素のQwen3.5-4B(~3.4GB)。多言語・汎用
    "qwen3.5:2b",                  # さらに軽量・最速(~2.7GB)。タイポ用途の退避先
    "gemma4:e2b",                  # Gemma4系。日本語の自然さ高(6GBではVRAM要確認)
]

DEFAULT_SETTINGS = {
    "hotkeys": {"business": "Ctrl+Alt+B", "typo": "Ctrl+Alt+T"},
    "server": {"host": "127.0.0.1", "port": 8765},
    "llm": {
        "provider": "ollama",
        # localhost だと Windows で IPv6(::1) に解決され Ollama(IPv4) と食い違って
        # 接続拒否が出ることがあるため 127.0.0.1 を既定にする。
        "endpoint": "http://127.0.0.1:11434",
        "model": "qwen3.5-jp-4b:q6",
        # Phase 0 検証で business は 0.4→0.3 に下げて意味反転(B09等)を抑制
        "temperature": {"business": 0.3, "typo": 0.2},
        "timeout_sec": 120,
        # 思考モデル(Qwen3等)の thinking 制御。false で高速化（typo: 41s→6s）
        "think": False,
        # 並列実行数の上限（§Phase 3）。超過分はキュー待ち
        "max_parallel": 2,
    },
    "clipboard": {
        "copy_result_on_complete": True,
        "restore_clipboard_after_capture": True,
        "capture_poll_interval_ms": 20,
        "capture_timeout_ms": 1000,
    },
    "sanitize": {
        "strip_preamble": True,
        "strip_wrapping_quotes": True,
        "preserve_linebreaks": True,
    },
    # プロンプト上書き（空なら prompts.DEFAULT_INSTRUCTIONS を使用）
    "prompts": {"business": "", "typo": ""},
    "corpus": {"enabled": False, "max_items": 200, "fewshot_count": 3, "encrypt": False},
    "history": {"enabled": True, "max_items": 10},
    "max_chars": 3000,
}


def _deep_merge(base, override):
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_settings():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                user = json.load(f)
            return _deep_merge(DEFAULT_SETTINGS, user)
        except (OSError, ValueError):
            # 壊れていたら既定値で起動（上書き保存はしない）
            return copy.deepcopy(DEFAULT_SETTINGS)
    # 初回は既定値を書き出す
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    save_settings(settings)
    return settings


def save_settings(settings):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
