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

    private void OnStartup(object sender, StartupEventArgs e)
    {
        var baseDir = AppContext.BaseDirectory;
        _settings = AppSettings.Load(Path.Combine(baseDir, "settings.json"));
        _client = new OllamaClient(_settings.Llm.Endpoint);
        _corpus = new CorpusStore(Path.Combine(baseDir, "corpus.json"));
        _service = new JobService(_settings, _client, _corpus);

        _main = new MainWindow(_settings, _client, OpenSettings);
        _main.Show();

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

    private void OnExit(object sender, ExitEventArgs e)
    {
        try { _loop.Stop(); _loop.Dispose(); }
        catch { /* ignore */ }
    }
}
