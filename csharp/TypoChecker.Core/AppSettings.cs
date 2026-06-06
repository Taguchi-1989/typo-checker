using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Unicode;

namespace TypoChecker.Core;

/// <summary>設定（Python版 app/config.py 相当）。System.Text.Json で読み書き。</summary>
public class LlmSettings
{
    // localhost は Windows で IPv6(::1) 優先解決→Ollama(IPv4)と食い違い接続拒否の恐れ。127.0.0.1 を既定に。
    public string Endpoint { get; set; } = "http://127.0.0.1:11434";
    public string Model { get; set; } = "qwen3.5-jp-4b:q6";
    public double TemperatureBusiness { get; set; } = 0.3;
    public double TemperatureTypo { get; set; } = 0.2;
    public bool? Think { get; set; } = false;
    public int MaxParallel { get; set; } = 2;
    public int TimeoutSec { get; set; } = 120;

    public double TemperatureFor(CorrectionMode m) =>
        m == CorrectionMode.Business ? TemperatureBusiness : TemperatureTypo;
}

public class SanitizeSettings
{
    public bool StripPreamble { get; set; } = true;
    public bool StripWrappingQuotes { get; set; } = true;
}

public class AppSettings
{
    /// <summary>§8.2 モデル候補（設定画面のドロップダウン用）。RTX 3060 / 6GB 向け、4B以下中心。</summary>
    public static readonly string[] ModelCandidates =
    {
        "qwen3.5-jp-4b:q6",   // dahara1 日本語特化 Qwen3.5-4B(Q6_K, ~3.8GB)。think=falseで高速・補正力◎
        "qwen3.5:4b",         // 素のQwen3.5-4B(~3.4GB)。多言語・汎用
        "qwen3.5:2b",         // さらに軽量・最速(~2.7GB)。タイポ用途の退避先
        "gemma4:e2b",         // Gemma4系。日本語の自然さ高(6GBではVRAM要確認)
    };

    public LlmSettings Llm { get; set; } = new();
    public SanitizeSettings Sanitize { get; set; } = new();
    public int MaxChars { get; set; } = 3000;
    public bool CopyResultOnComplete { get; set; } = true; // §7.3
    public bool CorpusEnabled { get; set; } = false;
    public int CorpusMaxItems { get; set; } = 200;
    public int CorpusFewshotCount { get; set; } = 3;
    public int HistoryMaxItems { get; set; } = 10;

    private static readonly JsonSerializerOptions Opts = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
        Encoder = JavaScriptEncoder.Create(UnicodeRanges.All),
    };

    /// <summary>読み込み（無ければ既定を書き出す。壊れていれば既定）。欠落キーは既定で補完。</summary>
    public static AppSettings Load(string path)
    {
        try
        {
            if (File.Exists(path))
                return JsonSerializer.Deserialize<AppSettings>(File.ReadAllText(path), Opts) ?? new AppSettings();
        }
        catch
        {
            return new AppSettings();
        }
        var s = new AppSettings();
        try { s.Save(path); } catch { /* 書けなくても既定で動く */ }
        return s;
    }

    public void Save(string path) =>
        File.WriteAllText(path, JsonSerializer.Serialize(this, Opts));
}
