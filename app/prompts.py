"""§8.4 プロンプト要件 ＋ §9 Corpus few-shot 注入。

INSTRUCTIONS には「条件」までを保持し、Corpus 用例 → 入力文 の順で
build_prompt() が動的に組み立てる。プロンプト本文は設定で上書き可能(§8.4 Phase 2)。
"""

# モード別の指示部（入力文タグは含めない）。設定画面から上書き可能。
DEFAULT_INSTRUCTIONS = {
    "business": (
        "あなたは日本語のビジネス文面補正アシスタントです。\n"
        "入力文を、相手に送れる自然な依頼文として整えてください。\n\n"
        "条件:\n"
        "- 意味を変えない\n"
        "- 肯定/否定や過不足を反転しない（例: 足りない→足りる は禁止）\n"
        "- 事実を追加しない\n"
        "- 過剰に堅くしない\n"
        "- 必要以上に長くしない\n"
        "- 依頼文として自然にする\n"
        "- 出力は日本語のみ。他言語を混在させない\n"
        "- 出力は修正後の本文のみ\n"
        "- 解説・前置き・引用符・箇条書きは出さない"
    ),
    "typo": (
        "あなたは日本語の校正アシスタントです。\n"
        "入力文の誤字・脱字・誤変換・明らかな句読点の乱れだけを修正してください。\n\n"
        "条件:\n"
        "- 文体を変えない\n"
        "- 表現を言い換えない\n"
        "- 丁寧語に変えない\n"
        "- 内容を要約しない\n"
        "- 事実を追加しない\n"
        "- 肯定/否定や過不足を反転しない\n"
        "- 改行・段落構造を維持する\n"
        "- 出力は日本語のみ。他言語を混在させない\n"
        "- 明らかな誤変換は修正する（例: 性式→正式）\n"
        "- 原文が壊れて意味不明な箇所は創作で補完しない\n"
        "- 出力は修正後の本文のみ\n"
        "- 解説・前置き・引用符は出さない\n"
        "- 確信がない箇所は無理に推測補正しない"
    ),
}

MODE_LABELS = {"business": "ビジネス依頼文化", "typo": "タイポ修正"}


def build_prompt(mode, text, instructions=None, fewshot=None):
    """モード別プロンプトを組み立てる。

    Args:
        mode: "business" | "typo"
        text: 入力（選択範囲）テキスト
        instructions: 指示部の上書き（None なら DEFAULT_INSTRUCTIONS）
        fewshot: Corpus 用例リスト [{source_text, accepted_text}, ...]（§9.1 方式A）
    """
    instr_map = instructions or DEFAULT_INSTRUCTIONS
    base = instr_map.get(mode, DEFAULT_INSTRUCTIONS[mode])

    parts = [base]

    if fewshot:
        lines = ["", "参考例（出力スタイルの参考のみ。内容・固有名詞は流用しない）:"]
        for ex in fewshot:
            src = (ex.get("source_text") or "").strip()
            acc = (ex.get("accepted_text") or "").strip()
            if not acc:
                continue
            if src:
                lines.append(f"入力: {src}")
                lines.append(f"出力: {acc}")
            else:
                lines.append(f"良い文例: {acc}")
            lines.append("")
        if len(lines) > 2:
            parts.append("\n".join(lines).rstrip())

    parts.append("\n入力文:\n" + text)
    return "\n".join(parts)
