#!/usr/bin/env python3
"""バックエンド起動ランチャ。

  python run_app.py

これを起動した状態で ahk/hotkeys.ahk を実行すると、
Ctrl+Alt+B / Ctrl+Alt+T で選択文の補正が回る。
"""

import os
import sys

# プロジェクトルートを import パスへ（app パッケージ解決のため）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.backend import main  # noqa: E402

if __name__ == "__main__":
    main()
