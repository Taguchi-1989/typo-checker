using System.Diagnostics;

namespace TypoChecker.Daemon;

/// <summary>非破壊キャプチャ（§5/§7.2 の移植）。本文は書き換えず Ctrl+C のみ、取得後に復元。</summary>
public static class SelectionCapturer
{
    /// <summary>選択範囲を取得して返す。取得失敗(空/タイムアウト)時は null。</summary>
    public static string? Capture(int timeoutMs = 1000, int pollMs = 20)
    {
        var saved = Native.GetClipboardText();   // 退避（テキストのみ）
        Native.SetClipboardText("");              // クリア
        Native.SendCtrlC();                       // 選択範囲をコピー

        string? captured = null;
        var sw = Stopwatch.StartNew();
        while (sw.ElapsedMilliseconds < timeoutMs)
        {
            Thread.Sleep(pollMs);
            var t = Native.GetClipboardText();
            if (!string.IsNullOrEmpty(t)) { captured = t; break; }
        }

        Native.SetClipboardText(saved ?? "");     // クリップボードを復元
        return string.IsNullOrWhiteSpace(captured) ? null : captured;
    }
}
