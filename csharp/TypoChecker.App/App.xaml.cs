using System.IO;
using System.Threading;
using System.Windows;
using TypoChecker.Core;
using TypoChecker.Daemon;

namespace TypoChecker.WpfApp;

public partial class App : Application
{
    private AppSettings _settings = null!;
    private OllamaClient _client = null!;
    private CorpusStore _corpus = null!;
    private JobService _service = null!;
    private HotkeyLoop _loop = null!;
    private MainWindow _main = null!;
    private TrayIcon _tray = null!;
    private bool _enabled = true;

    private void OnStartup(object sender, StartupEventArgs e)
    {
        var baseDir = AppContext.BaseDirectory;
        _settings = AppSettings.Load(Path.Combine(baseDir, "settings.json"));
        _client = new OllamaClient(_settings.Llm.Endpoint);
        _corpus = new CorpusStore(Path.Combine(baseDir, "corpus.json"));
        _service = new JobService(_settings, _client, _corpus);

        _main = new MainWindow(_settings, _client, OpenSettings);
        _main.Show();

        // [X] で閉じてもトレイ常駐（§6.2）
        _main.Closing += (s, ev) =>
        {
            if (_tray.Available)
            {
                ev.Cancel = true;
                _main.Hide();
            }
        };

        // タスクトレイ
        _tray = new TrayIcon(
            tooltip: $"文章補正ツール: {_settings.Llm.Model}",
            onShow: () => Dispatcher.Invoke(ShowMain),
            onToggle: () => Dispatcher.Invoke(ToggleEnabled),
            onQuit: () => Dispatcher.Invoke(() => Shutdown()),
            toggleLabel: () => _enabled ? "無効にする" : "有効にする");
        _tray.Show();

        _loop = new HotkeyLoop();
        _loop.OnHotkey += OnHotkey;
        var t = new Thread(() =>
        {
            if (!_loop.Run())
                Dispatcher.Invoke(() => _main.SetStatus(
                    "ホットキー登録に失敗（Ctrl+Alt+B/T が使用中）。AHK版を停止してください。"));
        })
        { IsBackground = true };
        t.SetApartmentState(ApartmentState.STA);
        t.Start();
    }

    // ホットキースレッドから発火 → キャプチャ即時 → UIスレッドで生成・表示
    private void OnHotkey(int id)
    {
        if (!_enabled)
        {
            Dispatcher.InvokeAsync(() => _main.SetStatus("無効中です（トレイから有効化できます）"));
            return;
        }
        var mode = id == HotkeyLoop.IdBusiness ? CorrectionMode.Business : CorrectionMode.Typo;
        var text = SelectionCapturer.Capture();

        Dispatcher.InvokeAsync(async () =>
        {
            if (string.IsNullOrWhiteSpace(text))
            {
                _main.SetStatus("取得失敗: 文章を選択してから押してください。");
                return;
            }
            _main.SetStatus($"補正中… [{mode.Label()}]");
            var job = await _service.RunAsync(mode, text!);

            if (job.Status == "done")
            {
                if (_settings.CopyResultOnComplete)
                {
                    TrySetClipboard(job.ResultText ?? "");
                    _main.SetStatus($"完了 [{mode.Label()}]（クリップボードにコピー）");
                }
                else
                {
                    _main.SetStatus($"完了 [{mode.Label()}]（コピーは結果ウィンドウから）");
                }
            }
            else
            {
                _main.SetStatus($"失敗: {job.ErrorMessage}");
            }

            var win = new ResultWindow(job, TrySetClipboard, OnAccept) { Owner = null };
            win.Show();
        });
    }

    private void OnAccept(Job job, bool accepted, string finalText)
    {
        job.Accepted = accepted;
        if (accepted && _settings.CorpusEnabled && job.Status == "done"
            && !string.IsNullOrWhiteSpace(finalText))
        {
            _corpus.Add(job.Mode, job.OriginalText, finalText,
                DateTime.Now.ToString("s"), _settings.CorpusMaxItems);
        }
    }

    private static void TrySetClipboard(string text)
    {
        try { Clipboard.SetText(text ?? ""); }
        catch { /* クリップボードが他プロセスにロックされている等は無視 */ }
    }

    private void OpenSettings()
    {
        var win = new SettingsWindow(_settings, _client, ApplySettings) { Owner = _main };
        win.ShowDialog();
    }

    // 設定保存後: エンドポイント/並列数を反映するためクライアントとサービスを作り直す
    private void ApplySettings()
    {
        _settings.Save(Path.Combine(AppContext.BaseDirectory, "settings.json"));
        _client = new OllamaClient(_settings.Llm.Endpoint);
        _service = new JobService(_settings, _client, _corpus);
        _main.Refresh(_settings, _client);
    }

    private void ShowMain()
    {
        _main.Show();
        if (_main.WindowState == WindowState.Minimized) _main.WindowState = WindowState.Normal;
        _main.Activate();
    }

    private void ToggleEnabled()
    {
        _enabled = !_enabled;
        _tray.SetTooltip(_enabled
            ? $"文章補正ツール: {_settings.Llm.Model}"
            : "文章補正ツール（無効中）");
        _main.SetStatus(_enabled ? "有効にしました" : "無効にしました");
    }

    private void OnExit(object sender, ExitEventArgs e)
    {
        try { _loop.Stop(); _loop.Dispose(); } catch { /* ignore */ }
        try { _tray.Stop(); } catch { /* ignore */ }
    }
}
