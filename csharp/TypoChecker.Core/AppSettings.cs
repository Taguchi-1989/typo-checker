using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Unicode;

namespace TypoChecker.Core;

/// <summary>設定（Python版 app/config.py 相当）。System.Text.Json で読み書き。</summary>
public class LlmSettings
{
    public string Endpoint { get; set; } = "http://localhost:11434";
    public string Model { get; set; } = "qwen3:8b";
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
    /// <summary>§8.2 モデル候補（設定画面のドロップダウン用）。</summary>
    public static readonly string[] ModelCandidates =
    {
        "qwen3:8b",
        "qwen2.5:7b-instruct",
        "gemma2:9b-instruct-q4_K_M",
        "gemma3:4b",
        "qwen2.5:3b-instruct-q4_K_M",
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
