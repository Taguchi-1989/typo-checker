"""§8.5 出力サニタイズ。

小型モデルは「修正文のみ」と指示しても前置き・装飾を付けがち。
クリップボードへ入れる前に除去する。ただし本文内の改行構造は保持する。

run_phase0.py の sanitize() と同一仕様（こちらが本体の正規実装）。
"""

import re

# 先頭に付きがちな前置き行のパターン
PREAMBLE_PATTERNS = [
    r"^(はい[、。]?\s*)",
    r"^(承知(いた)?しました[、。:：]?\s*)",
    r"^((修正|添削|校正)(いた)?しました[、。:：]?\s*)",
    r"^(修正(後の文|文|版|結果)?[はを]?[:：]?\s*)",
    r"^(以下が?.*?(です|になります)[:：]?\s*)",
    r"^(添削(結果)?[:：]?\s*)",
    r"^(校正(結果)?[:：]?\s*)",
]

# 全体を包みがちな引用符の対
_WRAP_PAIRS = [
    ("「", "」"), ("『", "』"), ('"', '"'), ("'", "'"),
    ("“", "”"), ("‘", "’"), ("`", "`"),
]


def sanitize(
    text,
    strip_preamble=True,
    strip_wrapping_quotes=True,
    preserve_linebreaks=True,
):
    """前置き・包み引用符・コードフェンスを除去。本文内の改行は保持する(§8.5)。

    Args:
        text: モデル生出力。
        strip_preamble: 先頭の前置き行を除去するか。
        strip_wrapping_quotes: 全体を包む引用符を一段剥がすか。
        preserve_linebreaks: 改行構造を保持するか（False でも現状は保持）。
    """
    if text is None:
        return ""
    t = text.strip()

    # thinkingモデル(Qwen3等)が本文へ思考を混ぜた場合の保険で <think>...</think> を除去
    t = re.sub(r"(?is)<think>.*?</think>", "", t).strip()

    # コードフェンス除去（```lang ... ```）
    if t.startswith("```"):
        t = re.sub(r"^```[^\n]*\n", "", t)
        t = re.sub(r"\n```$", "", t.rstrip())
        t = t.strip()

    # 先頭の前置き行を除去（複数回適用して連鎖した前置きにも対応）
    if strip_preamble:
        for _ in range(3):
            before = t
            for pat in PREAMBLE_PATTERNS:
                t = re.sub(pat, "", t, flags=re.IGNORECASE)
            t = t.strip()
            if t == before:
                break

    # 全体を包む引用符を一段だけ剥がす（本文内の改行は保持）
    if strip_wrapping_quotes:
        for open_q, close_q in _WRAP_PAIRS:
            if t.startswith(open_q) and t.endswith(close_q) and len(t) >= 2:
                inner = t[len(open_q):-len(close_q)]
                # 中に同種の閉じ引用符が無いときだけ剥がす（誤剥がし防止）
                if close_q not in inner or open_q == close_q:
                    t = inner.strip()
                break

    return t
