using System.Diagnostics;

namespace TypoChecker.WpfApp;

/// <summary>Windows トースト通知（Python版 app/notify.py の移植）。失敗は握りつぶす。</summary>
public static class NotifyHelper
{
    private const string AppId = @"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe";

    private const string PsScript = @"
$ErrorActionPreference='Stop'
try {
  $title = $env:TC_TOAST_TITLE
  $body  = $env:TC_TOAST_BODY
  [void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime]
  [void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType=WindowsRuntime]
  $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
  $t = '<toast><visual><binding template=""ToastGeneric""><text>' + [System.Security.SecurityElement]::Escape($title) + '</text><text>' + [System.Security.SecurityElement]::Escape($body) + '</text></binding></visual></toast>'
  $xml.LoadXml($t)
  $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
  [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:TC_TOAST_APPID).Show($toast)
} catch {}
";

    public static void Notify(string title, string body)
    {
        try
        {
            var psi = new ProcessStartInfo("powershell",
                "-NoProfile -NonInteractive -Command -")
            {
                RedirectStandardInput = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            psi.Environment["TC_TOAST_TITLE"] = title;
            psi.Environment["TC_TOAST_BODY"] = body;
            psi.Environment["TC_TOAST_APPID"] = AppId;
            var p = Process.Start(psi);
            if (p != null)
            {
                p.StandardInput.Write(PsScript);
                p.StandardInput.Close();
            }
        }
        catch
        {
            // 通知失敗は無視（結果ウィンドウが主フィードバック）
        }
    }
}
