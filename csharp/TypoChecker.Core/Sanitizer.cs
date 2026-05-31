using System.Text.RegularExpressions;

namespace TypoChecker.Core;

/// <summary>§8.5 出力サニタイズ（Python版 app/sanitize.py の移植）。</summary>
public static class Sanitizer
{
    private static readonly string[] PreamblePatterns =
    {
        @"^(はい[、。]?\s*)",
        @"^((修正|添削|校正)(いた)?しました[、。:：]?\s*)",
        @"^(修正(後の文|文|版|結果)?[はを]?[:：]?\s*)",
        @"^(以下が?.*?(です|になります)[:：]?\s*)",
        @"^(添削(結果)?[:：]?\s*)",
        @"^(校正(結果)?[:：]?\s*)",
    };

    private static readonly (string Open, string Close)[] WrapPairs =
    {
        ("「", "」"), ("『", "』"), ("\"", "\""), ("'", "'"),
        ("“", "”"), ("‘", "’"), ("`", "`"),
    };

    public static string Sanitize(string? text, bool stripPreamble = true, bool stripWrappingQuotes = true)
    {
        if (string.IsNullOrEmpty(text)) return "";
        var t = text.Trim();

        // 思考モデル(Qwen3等)の <think>...</think> を除去
        t = Regex.Replace(t, "<think>.*?</think>", "",
            RegexOptions.Singleline | RegexOptions.IgnoreCase).Trim();

        // コードフェンス除去
        if (t.StartsWith("```"))
        {
            t = Regex.Replace(t, "^```[^\n]*\n", "");
            t = Regex.Replace(t.TrimEnd(), "\n```$", "");
            t = t.Trim();
        }

        // 先頭の前置きを複数回除去
        if (stripPreamble)
        {
            for (var i = 0; i < 3; i++)
            {
                var before = t;
                foreach (var p in PreamblePatterns)
                    t = Regex.Replace(t, p, "", RegexOptions.IgnoreCase);
                t = t.Trim();
                if (t == before) break;
            }
        }

        // 全体を包む引用符を一段だけ剥がす（本文内の改行は保持）
        if (stripWrappingQuotes)
        {
            foreach (var (open, close) in WrapPairs)
            {
                if (t.Length >= 2 && t.StartsWith(open) && t.EndsWith(close))
                {
                    var inner = t.Substring(open.Length, t.Length - open.Length - close.Length);
                    if (!inner.Contains(close) || open == close)
                        t = inner.Trim();
                    break;
                }
            }
        }

        return t;
    }
}
