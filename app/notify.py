"""Notifier（§6.3 完了通知 / Windows通知）。

stdlib のみ。Windows の Toast を PowerShell 経由で出す。
環境によって失敗しうるため、失敗は握りつぶす（結果ウィンドウの前面化が主フィードバック）。
"""

import os
import subprocess

# PowerShell に同梱の AppID（インストール無しで Toast を出すための既知ID）
_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

_PS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
try {
  $title = $env:TC_TOAST_TITLE
  $body  = $env:TC_TOAST_BODY
  [void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime]
  [void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType=WindowsRuntime]
  $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
  $template = @"
<toast><visual><binding template="ToastGeneric"><text>$([System.Security.SecurityElement]::Escape($title))</text><text>$([System.Security.SecurityElement]::Escape($body))</text></binding></visual></toast>
"@
  $xml.LoadXml($template)
  $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
  [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:TC_TOAST_APPID).Show($toast)
} catch {}
"""


def notify(title, body):
    """Windows Toast を表示。失敗しても例外は投げない。"""
    if os.name != "nt":
        return
    env = dict(os.environ)
    env["TC_TOAST_TITLE"] = str(title)
    env["TC_TOAST_BODY"] = str(body)
    env["TC_TOAST_APPID"] = _APP_ID
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_SCRIPT],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:  # noqa: BLE001
        pass
