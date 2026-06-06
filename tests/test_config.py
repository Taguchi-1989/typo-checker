"""設定の読み書き・ディープマージ・壊れたファイルのフォールバック（§12.2）。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config  # noqa: E402


def _restore(backup):
    if backup is None:
        if os.path.exists(config.SETTINGS_PATH):
            os.remove(config.SETTINGS_PATH)
    else:
        with open(config.SETTINGS_PATH, "w", encoding="utf-8") as f:
            f.write(backup)


def main():
    backup = None
    if os.path.exists(config.SETTINGS_PATH):
        with open(config.SETTINGS_PATH, encoding="utf-8") as f:
            backup = f.read()
    try:
        # 1) 初回は既定値が書き出される
        if os.path.exists(config.SETTINGS_PATH):
            os.remove(config.SETTINGS_PATH)
        s = config.load_settings()
        assert os.path.exists(config.SETTINGS_PATH), "既定値が書き出されない"
        assert s["server"]["port"] == 8765
        # Phase 0/3 で更新した既定値
        assert s["llm"]["model"] == "qwen3.5-jp-4b:q6", s["llm"]["model"]
        assert s["llm"]["think"] is False
        assert s["llm"]["max_parallel"] == 2
        assert s["llm"]["temperature"]["business"] == 0.3
        assert s["history"]["enabled"] is True
        print("OK 初回既定生成（新デフォルト含む）")

        # 2) 部分上書き設定がディープマージされ、欠落フィールドは既定で補完
        partial = {"llm": {"model": "custom:1b"}, "max_chars": 500}
        with open(config.SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(partial, f)
        s = config.load_settings()
        assert s["llm"]["model"] == "custom:1b", s["llm"]["model"]
        assert s["llm"]["endpoint"] == "http://127.0.0.1:11434", "欠落が既定補完されない"
        assert s["max_chars"] == 500
        assert s["clipboard"]["capture_timeout_ms"] == 1000, "ネスト既定が消えた"
        print("OK ディープマージ")

        # 3) 壊れたJSONは既定値にフォールバック（例外を投げない）
        with open(config.SETTINGS_PATH, "w", encoding="utf-8") as f:
            f.write("{ this is broken")
        s = config.load_settings()
        assert s["server"]["port"] == 8765, "壊れファイルで既定に戻らない"
        print("OK 壊れファイルのフォールバック")

        print("\nCONFIG TEST PASSED")
    finally:
        _restore(backup)


if __name__ == "__main__":
    main()
