#Requires AutoHotkey v2.0
#SingleInstance Force
; ============================================================================
; Windows常駐型ローカルLLM文章補正ツール — ホットキー & 非破壊キャプチャ
; 仕様書 v0.2 §5 操作フロー / §7 クリップボード要件 に対応。
;
; 役割（§13）: Hotkey Manager + Clipboard Manager（退避・取得・反映待ち・復元）。
; LLM呼び出し・サニタイズ・結果表示・通知は run_app.py のPythonバックエンドが担当。
;
; 使い方:
;   1) python run_app.py を起動（待受 http://127.0.0.1:8765）
;   2) この .ahk をダブルクリックで常駐
;   3) 任意アプリで文章を選択し Ctrl+Alt+B / Ctrl+Alt+T
;
; 本文は一切書き換えない（Ctrl+C のみ）。取得後はクリップボードを元へ復元する。
; ============================================================================

SERVER_URL := "http://127.0.0.1:8765/job"
CAPTURE_TIMEOUT := 1.0   ; §7.2 反映待ちタイムアウト（秒）

^!b:: CaptureAndSend("business")
^!t:: CaptureAndSend("typo")

CaptureAndSend(mode) {
    global SERVER_URL, CAPTURE_TIMEOUT

    ; 1) 現在のクリップボードを退避（バイナリ含む全体）
    saved := ClipboardAll()

    ; 2) クリップボードを空にして Ctrl+C 送信（本文は書き換えない）
    A_Clipboard := ""
    Send("^c")

    ; 3) 反映待ち（テキストが入るまで。タイムアウトで取得失敗 §7.2 §10）
    if !ClipWait(CAPTURE_TIMEOUT, 0) {
        A_Clipboard := saved
        TrayTip("取得失敗", "文章を選択してから再実行してください", 1)
        return
    }

    text := A_Clipboard

    ; 4) 退避したクリップボードを復元（§5-6 / §7-4）
    A_Clipboard := saved

    ; 5) 空/非テキストは中止（§10）
    if (Trim(text) = "") {
        TrayTip("取得失敗", "テキストを取得できませんでした", 1)
        return
    }

    ; 6) ジョブとしてバックエンドへ送信（ここから先は Python が処理）
    title := WinGetTitle("A")
    if !PostJob(mode, text, title)
        TrayTip("送信失敗", "バックエンド(run_app.py)が起動しているか確認してください", 3)
}

PostJob(mode, text, windowTitle) {
    global SERVER_URL
    body := '{"mode":"' mode '","text":' JsonStr(text) ',"window_title":' JsonStr(windowTitle) '}'
    try {
        http := ComObject("WinHttp.WinHttpRequest.5.1")
        http.Open("POST", SERVER_URL, false)
        http.SetRequestHeader("Content-Type", "application/json; charset=utf-8")
        ; 日本語が文字化けしないよう UTF-8 バイト列(SAFEARRAY)で送る
        http.Send(Utf8Array(body))
        return (http.Status = 200)
    } catch {
        return false
    }
}

; 文字列を UTF-8 バイト列の SAFEARRAY(VT_UI1) に変換
Utf8Array(str) {
    n := StrPut(str, "UTF-8") - 1          ; 終端NULを除いたバイト数
    if (n < 0)
        n := 0
    buf := Buffer(n + 1)
    StrPut(str, buf, "UTF-8")
    arr := ComObjArray(0x11, n)            ; VT_UI1 の1次元配列
    loop n
        arr[A_Index - 1] := NumGet(buf, A_Index - 1, "UChar")
    return arr
}

; 文字列を JSON 文字列リテラル（前後の " 込み）へエスケープ
JsonStr(s) {
    s := StrReplace(s, "\", "\\")
    s := StrReplace(s, '"', '\"')
    s := StrReplace(s, "`r`n", "\n")
    s := StrReplace(s, "`n", "\n")
    s := StrReplace(s, "`r", "\n")
    s := StrReplace(s, "`t", "\t")
    return '"' s '"'
}
