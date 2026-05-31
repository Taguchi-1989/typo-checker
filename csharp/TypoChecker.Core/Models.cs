namespace TypoChecker.Core;

/// <summary>補正モード（§4）。</summary>
public enum CorrectionMode
{
    Business,
    Typo,
}

public static class CorrectionModeExtensions
{
    public static string Key(this CorrectionMode m) =>
        m == CorrectionMode.Business ? "business" : "typo";

    public static string Label(this CorrectionMode m) =>
        m == CorrectionMode.Business ? "ビジネス依頼文化" : "タイポ修正";
}

/// <summary>ジョブ（§12.1 / Python版 app/jobs.py 相当）。</summary>
public class Job
{
    public string JobId { get; } = Guid.NewGuid().ToString("N")[..12];
    public CorrectionMode Mode { get; init; }
    public string OriginalText { get; init; } = "";
    public string? ResultText { get; set; }
    public bool Sanitized { get; set; }
    public string Status { get; set; } = "queued"; // queued|running|done|failed
    public string? ErrorMessage { get; set; }
    public bool? Accepted { get; set; }            // §18.3 意味保存 Y/N
    public DateTime CreatedAt { get; } = DateTime.Now;
}
