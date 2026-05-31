"""OSクリップボード(ctypes)の往復テスト。Windowsでのみ実質的に検証する。

ユーザーの実クリップボードを退避し、テスト後に復元する。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import clipboard  # noqa: E402


def main():
    if not clipboard._IS_WIN:
        print("SKIP: 非Windows環境")
        return

    original = clipboard.get_clipboard_text()
    try:
        samples = [
            "これは補正後の文です。",
            "複数行\nのテキスト\nも保持",
            "絵文字😀と記号「」『』",
            "",
        ]
        for s in samples:
            ok = clipboard.set_clipboard_text(s)
            assert ok, f"set失敗: {s!r}"
            got = clipboard.get_clipboard_text()
            # 空文字は実装上 None または "" になりうる
            if s == "":
                assert got in ("", None), f"空クリップボード不一致: {got!r}"
            else:
                assert got == s, f"不一致: set={s!r} get={got!r}"
            print(f"OK {s!r}")
        print("\nCLIPBOARD TEST PASSED")
    finally:
        if original is not None:
            clipboard.set_clipboard_text(original)


if __name__ == "__main__":
    main()
