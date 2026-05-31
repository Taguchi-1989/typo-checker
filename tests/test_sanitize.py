"""§8.5 出力サニタイズの回帰テスト（Ollama不要）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.sanitize import sanitize  # noqa: E402

CASES = [
    ("はい、修正しました：本件についてご確認ください。", "本件についてご確認ください。"),
    ("校正しました。本文です", "本文です"),
    ("承知しました。これでお願いします", "これでお願いします"),
    ("```\n本文です\n```", "本文です"),
    ("```japanese\nコード風だが本文\n```", "コード風だが本文"),
    ("「依頼文です」", "依頼文です"),
    ("1行目\n2行目\n3行目", "1行目\n2行目\n3行目"),  # 改行保持
    ("以下が修正後の文です：\n本文", "本文"),
    # Qwen3等の思考ブロック除去
    ("<think>ここで推論する\n複数行</think>本文です", "本文です"),
    ("<think>考え中</think>\nはい、修正しました：直した文", "直した文"),
    ("普通の文。「引用」を含む。", "普通の文。「引用」を含む。"),  # 内側引用は剥がさない
    ("", ""),
    (None, ""),
]


def main():
    failures = 0
    for raw, expect in CASES:
        got = sanitize(raw)
        status = "OK " if got == expect else "NG "
        if got != expect:
            failures += 1
        print(f"{status}{raw!r} -> {got!r}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
