' ============================================================
' ローカルLLM文章補正ツール 起動スクリプト（自動起動／アイコン共用）
'  - バックエンドが既に動いていれば二重起動しない（ポート8765の /health で判定）
'  - ホットキー(AHK v2)は SingleInstance Force なので常に起動でOK
'  - バックエンドは pyw（コンソール無し・ユーザーの実Python）で常駐
' このスクリプト自身の場所を基準にするのでフォルダ移動しても動く。
' ============================================================
Option Explicit
Dim sh, fso, root, ahkExe, ahkScript, appScript

Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)

ahkScript = root & "\ahk\hotkeys.ahk"
appScript = root & "\run_app.py"

' --- ホットキー(AHK)を常駐起動（実行ファイル優先、無ければ関連付け） ---
ahkExe = "C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe"
If fso.FileExists(ahkScript) Then
    If fso.FileExists(ahkExe) Then
        sh.Run """" & ahkExe & """ """ & ahkScript & """", 0, False
    Else
        sh.Run """" & ahkScript & """", 0, False
    End If
End If

' --- バックエンド：既に動いていなければ起動（二重起動防止） ---
If (Not BackendUp()) And fso.FileExists(appScript) Then
    sh.Run "pyw -3 """ & appScript & """", 0, False
End If

' バックエンドが /health に応答していれば True
Function BackendUp()
    On Error Resume Next
    Dim http
    Set http = CreateObject("MSXML2.XMLHTTP")
    http.Open "GET", "http://127.0.0.1:8765/health", False
    http.Send
    BackendUp = (Err.Number = 0) And (http.Status = 200)
    On Error GoTo 0
End Function
