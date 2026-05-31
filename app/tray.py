"""タスクトレイ常駐（Phase 3 / §6.2）。依存ゼロ（ctypes + Win32 API）。

専用スレッドで非表示ウィンドウ＋メッセージループを回し、Shell_NotifyIcon で
トレイアイコンを出す。クリック/メニュー操作はコールバック（=バックエンドの
キューへ enqueue）で主スレッドへ渡す。Tk を直接触らないこと。

失敗時（非Windows等）は available=False になり、呼び出し側は通常ウィンドウ運用に
フォールバックする。
"""

import ctypes
import threading
from ctypes import wintypes

_IS_WIN = hasattr(ctypes, "WinDLL")

# --- Win32 定数 ---
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_COMMAND = 0x0111
WM_USER = 0x0400
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
TRAY_CALLBACK = WM_USER + 1

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x01, 0x02, 0x04
IDI_APPLICATION = 32512
MF_STRING, MF_SEPARATOR = 0x0000, 0x0800
TPM_RIGHTBUTTON, TPM_RETURNCMD = 0x0002, 0x0100

ID_SHOW, ID_TOGGLE, ID_QUIT = 1, 2, 3

if _IS_WIN:
    LRESULT = ctypes.c_ssize_t
    WNDPROCTYPE = ctypes.WINFUNCTYPE(
        LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
    )

    class WNDCLASS(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", WNDPROCTYPE),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HANDLE),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]

    class NOTIFYICONDATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd", wintypes.HWND),
            ("uID", wintypes.UINT),
            ("uFlags", wintypes.UINT),
            ("uCallbackMessage", wintypes.UINT),
            ("hIcon", wintypes.HICON),
            ("szTip", wintypes.WCHAR * 128),
            ("dwState", wintypes.DWORD),
            ("dwStateMask", wintypes.DWORD),
            ("szInfo", wintypes.WCHAR * 256),
            ("uVersion", wintypes.UINT),
            ("szInfoTitle", wintypes.WCHAR * 64),
            ("dwInfoFlags", wintypes.DWORD),
        ]

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _shell32 = ctypes.WinDLL("shell32", use_last_error=True)

    # 64bitで lparam/ハンドルが溢れないよう argtypes/restype を明示する
    _W = wintypes
    _kernel32.GetModuleHandleW.argtypes = [_W.LPCWSTR]
    _kernel32.GetModuleHandleW.restype = _W.HMODULE
    _user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
    _user32.RegisterClassW.restype = _W.ATOM
    _user32.CreateWindowExW.argtypes = [
        _W.DWORD, _W.LPCWSTR, _W.LPCWSTR, _W.DWORD, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, _W.HWND, _W.HMENU, _W.HINSTANCE, _W.LPVOID,
    ]
    _user32.CreateWindowExW.restype = _W.HWND
    _user32.DefWindowProcW.argtypes = [_W.HWND, _W.UINT, _W.WPARAM, _W.LPARAM]
    _user32.DefWindowProcW.restype = LRESULT
    _user32.GetMessageW.argtypes = [ctypes.POINTER(_W.MSG), _W.HWND, _W.UINT, _W.UINT]
    _user32.GetMessageW.restype = ctypes.c_int
    _user32.TranslateMessage.argtypes = [ctypes.POINTER(_W.MSG)]
    _user32.DispatchMessageW.argtypes = [ctypes.POINTER(_W.MSG)]
    _user32.DispatchMessageW.restype = LRESULT
    _user32.PostMessageW.argtypes = [_W.HWND, _W.UINT, _W.WPARAM, _W.LPARAM]
    _user32.PostMessageW.restype = _W.BOOL
    _user32.PostQuitMessage.argtypes = [ctypes.c_int]
    _user32.LoadIconW.argtypes = [_W.HINSTANCE, _W.LPCWSTR]
    _user32.LoadIconW.restype = _W.HICON
    _user32.CreatePopupMenu.restype = _W.HMENU
    _user32.AppendMenuW.argtypes = [_W.HMENU, _W.UINT, ctypes.c_size_t, _W.LPCWSTR]
    _user32.AppendMenuW.restype = _W.BOOL
    _user32.TrackPopupMenu.argtypes = [
        _W.HMENU, _W.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, _W.HWND, _W.LPVOID,
    ]
    _user32.TrackPopupMenu.restype = ctypes.c_int  # TPM_RETURNCMD でコマンドIDを返す
    _user32.DestroyMenu.argtypes = [_W.HMENU]
    _user32.GetCursorPos.argtypes = [ctypes.POINTER(_W.POINT)]
    _user32.SetForegroundWindow.argtypes = [_W.HWND]
    _shell32.Shell_NotifyIconW.argtypes = [_W.DWORD, ctypes.POINTER(NOTIFYICONDATA)]
    _shell32.Shell_NotifyIconW.restype = _W.BOOL

    def _make_int_resource(i):
        return ctypes.cast(ctypes.c_void_p(i), wintypes.LPCWSTR)


class TrayIcon:
    """トレイアイコン。show()でスレッド起動、stop()で終了。

    callbacks: on_show / on_toggle / on_quit （いずれもトレイスレッドから呼ばれる）
    """

    def __init__(self, tooltip="文章補正ツール", on_show=None, on_toggle=None, on_quit=None):
        self.available = _IS_WIN
        self._tooltip = tooltip
        self._on_show = on_show or (lambda: None)
        self._on_toggle = on_toggle or (lambda: None)
        self._on_quit = on_quit or (lambda: None)
        self._enabled_label = "無効にする"
        self.hwnd = None
        self._thread = None
        self._wndproc_ref = None  # GC防止のため保持

    def show(self):
        if not self.available:
            return False
        self._thread = threading.Thread(target=self._run, name="tc-tray", daemon=True)
        self._thread.start()
        return True

    def set_tooltip(self, text):
        self._tooltip = text
        if self.hwnd:
            self._modify_tip(text)

    def set_enabled_label(self, label):
        self._enabled_label = label

    def stop(self):
        if self.hwnd:
            try:
                _user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
            except Exception:  # noqa: BLE001
                pass

    # --- 内部（トレイスレッド） ---------------------------------------
    def _run(self):
        try:
            self._create_window()
            self._add_icon()
            self._message_loop()
        except Exception:  # noqa: BLE001
            self.available = False

    def _create_window(self):
        hinst = _kernel32.GetModuleHandleW(None)
        self._wndproc_ref = WNDPROCTYPE(self._wndproc)
        cls_name = "TypoCheckerTrayWnd"
        wc = WNDCLASS()
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = hinst
        wc.lpszClassName = cls_name
        _user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = _user32.CreateWindowExW(
            0, cls_name, "TypoCheckerTray", 0, 0, 0, 0, 0, None, None, hinst, None
        )

    def _nid(self, flags):
        nid = NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = flags
        return nid

    def _add_icon(self):
        hicon = _user32.LoadIconW(None, _make_int_resource(IDI_APPLICATION))
        nid = self._nid(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        nid.uCallbackMessage = TRAY_CALLBACK
        nid.hIcon = hicon
        nid.szTip = self._tooltip[:127]
        _shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def _modify_tip(self, text):
        hicon = _user32.LoadIconW(None, _make_int_resource(IDI_APPLICATION))
        nid = self._nid(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        nid.uCallbackMessage = TRAY_CALLBACK
        nid.hIcon = hicon
        nid.szTip = text[:127]
        _shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def _remove_icon(self):
        nid = self._nid(0)
        _shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))

    def _show_menu(self):
        hmenu = _user32.CreatePopupMenu()
        _user32.AppendMenuW(hmenu, MF_STRING, ID_SHOW, "表示")
        _user32.AppendMenuW(hmenu, MF_STRING, ID_TOGGLE, self._enabled_label)
        _user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
        _user32.AppendMenuW(hmenu, MF_STRING, ID_QUIT, "終了")
        pt = wintypes.POINT()
        _user32.GetCursorPos(ctypes.byref(pt))
        _user32.SetForegroundWindow(self.hwnd)
        cmd = _user32.TrackPopupMenu(
            hmenu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, 0, self.hwnd, None
        )
        _user32.DestroyMenu(hmenu)
        if cmd == ID_SHOW:
            self._on_show()
        elif cmd == ID_TOGGLE:
            self._on_toggle()
        elif cmd == ID_QUIT:
            self._on_quit()

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == TRAY_CALLBACK:
            if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self._on_show()
            elif lparam == WM_RBUTTONUP:
                self._show_menu()
            return 0
        if msg == WM_DESTROY:
            self._remove_icon()
            _user32.PostQuitMessage(0)
            return 0
        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _message_loop(self):
        msg = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))


if __name__ == "__main__":
    # 単体スモーク: 2秒だけアイコンを出して消す
    import time

    t = TrayIcon(tooltip="トレイ自己テスト")
    print("available:", t.available, "/ show:", t.show())
    time.sleep(2)
    t.stop()
    time.sleep(0.5)
    print("done")
