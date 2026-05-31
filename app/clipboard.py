"""Windows クリップボード（OSネイティブ / ctypes）。

tkinter のクリップボードは Windows では遅延レンダリング方式で、Tk の
イベントループが回っている間しか他アプリへ貼り付けできない。本ツールは
「別アプリで Ctrl+V」が中核なので、OS クリップボードへ直接書き込む。

set_clipboard_text() が成功すれば、その後はバックエンドの状態に依存せず
貼り付けできる。非Windows・失敗時は False を返し、呼び出し側が代替手段へ。
"""

import ctypes
import time
from ctypes import wintypes

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

_IS_WIN = hasattr(ctypes, "WinDLL")

if _IS_WIN:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _user32.OpenClipboard.argtypes = [wintypes.HWND]
    _user32.OpenClipboard.restype = wintypes.BOOL
    _user32.CloseClipboard.argtypes = []
    _user32.CloseClipboard.restype = wintypes.BOOL
    _user32.EmptyClipboard.argtypes = []
    _user32.EmptyClipboard.restype = wintypes.BOOL
    _user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    _user32.SetClipboardData.restype = wintypes.HANDLE
    _user32.GetClipboardData.argtypes = [wintypes.UINT]
    _user32.GetClipboardData.restype = wintypes.HANDLE

    _kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    _kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    _kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    _kernel32.GlobalLock.restype = wintypes.LPVOID
    _kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    _kernel32.GlobalUnlock.restype = wintypes.BOOL


def _open_clipboard(retries=10, delay=0.02):
    """他プロセスが握っていることがあるのでリトライ付きで開く。"""
    for _ in range(retries):
        if _user32.OpenClipboard(None):
            return True
        time.sleep(delay)
    return False


def set_clipboard_text(text):
    """OS クリップボードへ UTF-16 テキストを書き込む。成功で True。"""
    if not _IS_WIN:
        return False
    if not isinstance(text, str):
        text = "" if text is None else str(text)

    data = text.encode("utf-16-le") + b"\x00\x00"
    size = len(data)

    if not _open_clipboard():
        return False
    try:
        _user32.EmptyClipboard()
        h_global = _kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not h_global:
            return False
        ptr = _kernel32.GlobalLock(h_global)
        if not ptr:
            return False
        ctypes.memmove(ptr, data, size)
        _kernel32.GlobalUnlock(h_global)
        # 成功後はメモリ所有権がシステムへ移る（解放しない）
        if not _user32.SetClipboardData(CF_UNICODETEXT, h_global):
            return False
        return True
    finally:
        _user32.CloseClipboard()


def get_clipboard_text():
    """OS クリップボードのテキストを取得（無ければ None）。テスト/復元用。"""
    if not _IS_WIN:
        return None
    if not _open_clipboard():
        return None
    try:
        handle = _user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = _kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.c_wchar_p(ptr).value
        finally:
            _kernel32.GlobalUnlock(handle)
    finally:
        _user32.CloseClipboard()
