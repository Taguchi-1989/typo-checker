using System.Text;

namespace TypoChecker.Core;

/// <summary>§8.4 プロンプト（Python版 app/prompts.py の移植・プロンプトv2反映済み）。</summary>
public static class Prompts
{
    public static readonly IReadOnlyDictionary<CorrectionMode, string> DefaultInstructions =
        new Dictionary<CorrectionMode, string>
        {
            [CorrectionMode.Business] = string.Join("\n", new[]
            {
                "あなたは日本語のビジネス文面補正アシスタントです。",
                "入力文を、相手に送れる自然な依頼文として整えてください。",
                "",
                "条件:",
                "- 意味を変えない",
                "- 肯定/否定や過不足を反転しない（例: 足りない→足りる は禁止）",
                "- 事実を追加しない",
                "- 過剰に堅くしない",
                "- 必要以上に長くしない",
                "- 依頼文として自然にする",
                "- 出力は日本語のみ。他言語を混在させない",
                "- 出力は修正後の本文のみ",
                "- 解説・前置き・引用符・箇条書きは出さない",
            }),
            [CorrectionMode.Typo] = string.Join("\n", new[]
            {
                "あなたは日本語の校正アシスタントです。",
                "入力文の誤字・脱字・誤変換・明らかな句読点の乱れだけを修正してください。",
                "",
                "条件:",
                "- 文体を変えない",
                "- 表現を言い換えない",
                "- 丁寧語に変えない",
                "- 内容を要約しない",
                "- 事実を追加しない",
                "- 肯定/否定や過不足を反転しない",
                "- 改行・段落構造を維持する",
                "- 出力は日本語のみ。他言語を混在させない",
                "- 明らかな誤変換は修正する（例: 性式→正式）",
                "- 原文が壊れて意味不明な箇所は創作で補完しない",
                "- 出力は修正後の本文のみ",
                "- 解説・前置き・引用符は出さない",
                "- 確信がない箇所は無理に推測補正しない",
            }),
        };

    public static string BuildPrompt(CorrectionMode mode, string text) =>
        BuildPrompt(mode, text, null);

    /// <summary>Corpus 用例（§9.1 方式A）を few-shot として注入してプロンプトを組み立てる。</summary>
    public static string BuildPrompt(CorrectionMode mode, string text, IEnumerable<CorpusItem>? fewshot)
    {
        var sb = new StringBuilder(DefaultInstructions[mode]);

        var examples = fewshot?
            .Where(e => !string.IsNullOrWhiteSpace(e.AcceptedText))
            .ToList();
        if (examples is { Count: > 0 })
        {
            sb.Append("\n\n参考例（出力スタイルの参考のみ。内容・固有名詞は流用しない）:");
            foreach (var e in examples)
            {
                if (!string.IsNullOrWhiteSpace(e.SourceText))
                    sb.Append($"\n入力: {e.SourceText.Trim()}\n出力: {e.AcceptedText.Trim()}");
                else
                    sb.Append($"\n良い文例: {e.AcceptedText.Trim()}");
            }
        }

        sb.Append("\n\n入力文:\n").Append(text);
        return sb.ToString();
    }
}
