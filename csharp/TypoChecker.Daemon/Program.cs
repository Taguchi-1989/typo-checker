using System.Text;
using TypoChecker.Core;
using TypoChecker.Daemon;

// グローバルホットキー常駐デーモン（C#移植の動作確認用・コンソール）。
//   Ctrl+Alt+B = ビジネス依頼文化 / Ctrl+Alt+T = タイポ修正 / Ctrl+C = 終了
// 結果はコンソール出力＋クリップボードへコピー（GUIは別途 WPF で実装予定）。

Console.OutputEncoding = Encoding.UTF8;

// 自己テスト: クリップボードP/Invokeの往復確認（キー押下不要）
//   dotnet run --project TypoChecker.Daemon -- selftest
if (args.Length > 0 && args[0] == "selftest")
{
    var original = Native.GetClipboardText();
    var sample = "クリップボード往復テスト：日本語と記号「」😀";
    var setOk = Native.SetClipboardText(sample);
    var back = Native.GetClipboardText();
    Native.SetClipboardText(original ?? ""); // 元へ復元
    var pass = setOk && back == sample;
    Console.WriteLine(pass ? $"OK clipboard roundtrip: {back}" : $"NG (set={setOk}): {back}");
    return pass ? 0 : 1;
}

var settingsPath = Path.Combine(AppContext.BaseDirectory, "settings.json");
var settings = AppSettings.Load(settingsPath);
var client = new OllamaClient(settings.Llm.Endpoint);
var service = new JobService(settings, client);

Console.WriteLine("=== 文章補正デーモン (C#) ===");
Console.WriteLine($"モデル: {settings.Llm.Model} / エンドポイント: {settings.Llm.Endpoint}");
Console.WriteLine("Ctrl+Alt+B=ビジネス / Ctrl+Alt+T=タイポ  （Ctrl+C で終了）");
Console.WriteLine(await client.CheckConnectionAsync()
    ? "接続OK"
    : "[警告] Ollama に接続できません（起動を確認してください）");

using var loop = new HotkeyLoop();

loop.OnHotkey += id =>
{
    var mode = id == HotkeyLoop.IdBusiness ? CorrectionMode.Business : CorrectionMode.Typo;

    // キャプチャはこのスレッドで即時（対象アプリにフォーカスがある間に）
    var text = SelectionCapturer.Capture();
    if (string.IsNullOrWhiteSpace(text))
    {
        Console.WriteLine("取得失敗: 文章を選択してから押してください。");
        return;
    }
    Console.WriteLine($"\n[{mode.Label()}] 原文: {text}");

    // 生成は非同期（ループを長くブロックしない）
    _ = Task.Run(async () =>
    {
        var job = await service.RunAsync(mode, text);
        if (job.Status == "done")
        {
            Native.SetClipboardText(job.ResultText ?? "");
            Console.WriteLine($"生成: {job.ResultText}");
            Console.WriteLine("→ クリップボードにコピーしました（元の場所で Ctrl+V）");
        }
        else
        {
            Console.WriteLine($"失敗: {job.ErrorMessage}");
        }
    });
};

Console.CancelKeyPress += (_, e) =>
{
    e.Cancel = true; // 即時killせずクリーンに終了
    loop.Stop();
};

if (!loop.Run())
{
    Console.WriteLine("[エラー] ホットキー登録に失敗（他アプリが Ctrl+Alt+B/T を使用中の可能性）。");
    return 1;
}

Console.WriteLine("終了しました。");
return 0;
