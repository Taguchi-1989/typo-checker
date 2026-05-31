namespace TypoChecker.Daemon;

/// <summary>グローバルホットキー常駐（AHK ホットキーの C# 置換 §14）。

/// RegisterHotKey(hWnd=0) でスレッドキューに WM_HOTKEY を受け、GetMessage ループで拾う。
/// Run() は呼び出しスレッドをブロックする（そのスレッドにホットキーが紐づく）。
/// </summary>
public sealed class HotkeyLoop : IDisposable
{
    public const int IdBusiness = 1;
    public const int IdTypo = 2;

    /// <summary>ホットキー押下時に発火（引数 = Id）。ループスレッドで呼ばれる。</summary>
    public event Action<int>? OnHotkey;

    private uint _threadId;
    private bool _registered;

    public bool Run()
    {
        _threadId = Native.GetCurrentThreadId();
        var ok1 = Native.RegisterHotKey(IntPtr.Zero, IdBusiness, Native.MOD_CONTROL | Native.MOD_ALT, Native.VK_B);
        var ok2 = Native.RegisterHotKey(IntPtr.Zero, IdTypo, Native.MOD_CONTROL | Native.MOD_ALT, Native.VK_T);
        _registered = ok1 && ok2;
        if (!_registered) return false; // 既に他アプリが同じホットキーを掴んでいる等

        while (Native.GetMessageW(out var msg, IntPtr.Zero, 0, 0) > 0)
        {
            if (msg.message == Native.WM_HOTKEY)
                OnHotkey?.Invoke(msg.wParam.ToInt32());
        }
        return true;
    }

    /// <summary>別スレッドからループを終了させる。</summary>
    public void Stop()
    {
        if (_threadId != 0)
            Native.PostThreadMessageW(_threadId, Native.WM_QUIT, IntPtr.Zero, IntPtr.Zero);
    }

    public void Dispose()
    {
        if (_registered)
        {
            Native.UnregisterHotKey(IntPtr.Zero, IdBusiness);
            Native.UnregisterHotKey(IntPtr.Zero, IdTypo);
            _registered = false;
        }
    }
}
