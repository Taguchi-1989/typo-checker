using System.Runtime.InteropServices;

namespace TypoChecker.WpfApp;

/// <summary>タスクトレイ常駐（Win32 / 依存ゼロ。Python版 app/tray.py の移植）。

/// 専用スレッドで非表示ウィンドウ＋メッセージループを回し Shell_NotifyIcon でアイコン表示。
/// クリック/メニュー操作は Action コールバックで通知（呼び出し側で Dispatcher へ marshal）。
/// </summary>
public sealed class TrayIcon : IDisposable
{
    private const int WM_DESTROY = 0x0002, WM_CLOSE = 0x0010;
    private const uint WM_USER = 0x0400;
    private const uint WM_LBUTTONUP = 0x0202, WM_LBUTTONDBLCLK = 0x0203, WM_RBUTTONUP = 0x0205;
    private const uint TRAY_CALLBACK = WM_USER + 1;
    private const uint NIM_ADD = 0, NIM_MODIFY = 1, NIM_DELETE = 2;
    private const uint NIF_MESSAGE = 0x01, NIF_ICON = 0x02, NIF_TIP = 0x04;
    private const int IDI_APPLICATION = 32512;
    private const uint MF_STRING = 0x0000, MF_SEPARATOR = 0x0800;
    private const uint TPM_RIGHTBUTTON = 0x0002, TPM_RETURNCMD = 0x0100;
    private const uint ID_SHOW = 1, ID_TOGGLE = 2, ID_QUIT = 3;

    private readonly string _tooltip;
    private readonly Action _onShow, _onToggle, _onQuit;
    private readonly Func<string> _toggleLabel;
    private IntPtr _hwnd;
    private WndProc? _wndProc; // GC防止のため保持
    private Thread? _thread;

    public bool Available { get; private set; } = true;

    public TrayIcon(string tooltip, Action onShow, Action onToggle, Action onQuit, Func<string> toggleLabel)
    {
        _tooltip = tooltip;
        _onShow = onShow;
        _onToggle = onToggle;
        _onQuit = onQuit;
        _toggleLabel = toggleLabel;
    }

    public void Show()
    {
        _thread = new Thread(Run) { IsBackground = true };
        _thread.SetApartmentState(ApartmentState.STA);
        _thread.Start();
    }

    public void Stop()
    {
        if (_hwnd != IntPtr.Zero)
            PostMessageW(_hwnd, WM_CLOSE, IntPtr.Zero, IntPtr.Zero);
    }

    public void Dispose() => Stop();

    private void Run()
    {
        try
        {
            var hinst = GetModuleHandleW(null);
            _wndProc = WndProcImpl;
            var cls = new WNDCLASS
            {
                lpfnWndProc = Marshal.GetFunctionPointerForDelegate(_wndProc),
                hInstance = hinst,
                lpszClassName = "TypoCheckerTrayWnd",
            };
            RegisterClassW(ref cls);
            _hwnd = CreateWindowExW(0, cls.lpszClassName, "TypoCheckerTray", 0,
                0, 0, 0, 0, IntPtr.Zero, IntPtr.Zero, hinst, IntPtr.Zero);
            AddOrModify(NIM_ADD, _tooltip);

            while (GetMessageW(out var msg, IntPtr.Zero, 0, 0) > 0)
            {
                TranslateMessage(ref msg);
                DispatchMessageW(ref msg);
            }
        }
        catch
        {
            Available = false;
        }
    }

    private void AddOrModify(uint action, string tip)
    {
        var nid = new NOTIFYICONDATA
        {
            cbSize = Marshal.SizeOf<NOTIFYICONDATA>(),
            hWnd = _hwnd,
            uID = 1,
            uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP,
            uCallbackMessage = TRAY_CALLBACK,
            hIcon = LoadIconW(IntPtr.Zero, (IntPtr)IDI_APPLICATION),
            szTip = tip.Length > 127 ? tip[..127] : tip,
        };
        Shell_NotifyIconW(action, ref nid);
    }

    public void SetTooltip(string tip)
    {
        if (_hwnd != IntPtr.Zero) AddOrModify(NIM_MODIFY, tip);
    }

    private void RemoveIcon()
    {
        var nid = new NOTIFYICONDATA { cbSize = Marshal.SizeOf<NOTIFYICONDATA>(), hWnd = _hwnd, uID = 1 };
        Shell_NotifyIconW(NIM_DELETE, ref nid);
    }

    private void ShowMenu()
    {
        var hMenu = CreatePopupMenu();
        AppendMenuW(hMenu, MF_STRING, (UIntPtr)ID_SHOW, "表示");
        AppendMenuW(hMenu, MF_STRING, (UIntPtr)ID_TOGGLE, _toggleLabel());
        AppendMenuW(hMenu, MF_SEPARATOR, UIntPtr.Zero, null);
        AppendMenuW(hMenu, MF_STRING, (UIntPtr)ID_QUIT, "終了");
        GetCursorPos(out var pt);
        SetForegroundWindow(_hwnd);
        var cmd = TrackPopupMenu(hMenu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.X, pt.Y, 0, _hwnd, IntPtr.Zero);
        DestroyMenu(hMenu);
        if (cmd == (int)ID_SHOW) _onShow();
        else if (cmd == (int)ID_TOGGLE) _onToggle();
        else if (cmd == (int)ID_QUIT) _onQuit();
    }

    private IntPtr WndProcImpl(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam)
    {
        if (msg == TRAY_CALLBACK)
        {
            var ev = (uint)(lParam.ToInt64() & 0xFFFF);
            if (ev == WM_LBUTTONUP || ev == WM_LBUTTONDBLCLK) _onShow();
            else if (ev == WM_RBUTTONUP) ShowMenu();
            return IntPtr.Zero;
        }
        if (msg == WM_DESTROY)
        {
            RemoveIcon();
            PostQuitMessage(0);
            return IntPtr.Zero;
        }
        return DefWindowProcW(hWnd, msg, wParam, lParam);
    }

    // --- Win32 ---
    private delegate IntPtr WndProc(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct WNDCLASS
    {
        public uint style;
        public IntPtr lpfnWndProc;
        public int cbClsExtra;
        public int cbWndExtra;
        public IntPtr hInstance;
        public IntPtr hIcon;
        public IntPtr hCursor;
        public IntPtr hbrBackground;
        public string? lpszMenuName;
        public string lpszClassName;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct NOTIFYICONDATA
    {
        public int cbSize;
        public IntPtr hWnd;
        public uint uID;
        public uint uFlags;
        public uint uCallbackMessage;
        public IntPtr hIcon;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string szTip;
        public uint dwState;
        public uint dwStateMask;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)] public string szInfo;
        public uint uVersion;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)] public string szInfoTitle;
        public uint dwInfoFlags;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct POINT { public int X; public int Y; }

    [StructLayout(LayoutKind.Sequential)]
    private struct MSG
    {
        public IntPtr hwnd; public uint message; public IntPtr wParam; public IntPtr lParam;
        public uint time; public int ptX; public int ptY;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr GetModuleHandleW(string? name);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern ushort RegisterClassW(ref WNDCLASS wc);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr CreateWindowExW(uint exStyle, string className, string windowName,
        uint style, int x, int y, int w, int h, IntPtr parent, IntPtr menu, IntPtr hInstance, IntPtr param);
    [DllImport("user32.dll")]
    private static extern IntPtr DefWindowProcW(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")]
    private static extern int GetMessageW(out MSG msg, IntPtr hWnd, uint min, uint max);
    [DllImport("user32.dll")]
    private static extern bool TranslateMessage(ref MSG msg);
    [DllImport("user32.dll")]
    private static extern IntPtr DispatchMessageW(ref MSG msg);
    [DllImport("user32.dll")]
    private static extern bool PostMessageW(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")]
    private static extern void PostQuitMessage(int exitCode);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr LoadIconW(IntPtr hInstance, IntPtr name);
    [DllImport("user32.dll")]
    private static extern IntPtr CreatePopupMenu();
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern bool AppendMenuW(IntPtr hMenu, uint flags, UIntPtr idNewItem, string? newItem);
    [DllImport("user32.dll")]
    private static extern int TrackPopupMenu(IntPtr hMenu, uint flags, int x, int y, int reserved, IntPtr hWnd, IntPtr rect);
    [DllImport("user32.dll")]
    private static extern bool DestroyMenu(IntPtr hMenu);
    [DllImport("user32.dll")]
    private static extern bool GetCursorPos(out POINT pt);
    [DllImport("user32.dll")]
    private static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    private static extern bool Shell_NotifyIconW(uint message, ref NOTIFYICONDATA data);
}
