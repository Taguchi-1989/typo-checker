# Phase 4: C#/.NET 移植（着手）

仕様 §14 / §15 Phase 4。プロトタイプ（AHK + Python）の挙動が固まったので、
本実装を C#/.NET へ移植する。**移植＝実質作り直し**（AHKロジックは流用不可前提）。

> 状態: **コア＋GUI＋OS統合まで移植（.NET 8 / 28テスト緑・全ビルド成功・起動確認済）**。
> Core(Sanitizer/Prompts/OllamaClient/Models/AppSettings/CorpusStore/JobService) ＋
> Daemon(ホットキー/非破壊キャプチャ/クリップボード) ＋ WPF(状態・結果・設定ウィンドウ・トレイ常駐)。
> 残: 通知・履歴・処理中インジケータ・パッケージング。実押下/GUI操作の確認は実機で。

## 構成

```
csharp/
  TypoChecker.Core/     移植済みの純ロジック（依存なし）
    Models.cs           CorrectionMode / Job（§12.1）
    Sanitizer.cs        §8.5 出力サニタイズ（app/sanitize.py 相当）
    Prompts.cs          §8.4 プロンプトv2（app/prompts.py 相当）
    OllamaClient.cs     §8.1 Ollama 呼び出し（app/llm.py 相当・think対応）
  TypoChecker.Cli/      動作確認用コンソール（生成→サニタイズを通す）
  TypoChecker.Tests/    xUnit。Sanitizer 回帰（test_sanitize.py 相当）
```

## ビルド・実行（要 .NET 8 SDK）

```
cd csharp
dotnet test TypoChecker.Tests/TypoChecker.Tests.csproj      # 19テスト
dotnet run --project TypoChecker.Cli -- typo "なおしたいテキスト"
echo 雑なメモ | dotnet run --project TypoChecker.Cli -- business

# ホットキー常駐デーモン（Ctrl+Alt+B/T）。※AHK版が動いているとホットキー競合で登録失敗するので先に停止
dotnet run --project TypoChecker.Daemon
dotnet run --project TypoChecker.Daemon -- selftest          # クリップボード往復の自己テスト

# WPF GUI 版（状態ウィンドウ＋結果ウィンドウ）。※同じくAHK版を停止してから
dotnet run --project TypoChecker.App
#   ビルド済みexe: TypoChecker.App\bin\Release\net8.0-windows\TypoChecker.App.exe
```

> 検証済み: .NET 8.0.421 で `dotnet test` 15件緑、CLI は実 Ollama(qwen3:8b) で動作確認。

## Python → C# 対応表

| Python (プロトタイプ) | C# (本実装) | 状態 |
|---|---|---|
| app/sanitize.py | TypoChecker.Core/Sanitizer.cs | ✅ 移植 |
| app/prompts.py | TypoChecker.Core/Prompts.cs | ✅ 移植 |
| app/llm.py | TypoChecker.Core/OllamaClient.cs | ✅ 移植 |
| app/jobs.py | TypoChecker.Core/Models.cs (Job) | ✅ 移植 |
| app/config.py | TypoChecker.Core/AppSettings.cs | ✅ 移植 |
| app/corpus.py | TypoChecker.Core/CorpusStore.cs | ✅ 移植 |
| app/clipboard.py | TypoChecker.Daemon/Native.cs (Win32 Clipboard) | ✅ 移植(往復確認済) |
| app/notify.py | Windows トースト（CommunityToolkit等） | ⏳ 未 |
| ahk/hotkeys.ahk | TypoChecker.Daemon/HotkeyLoop.cs + SelectionCapturer.cs | ✅ 移植(要実機での実押下確認) |
| app/tray.py | TypoChecker.App/TrayIcon.cs (Win32) | ✅ 移植([X]で常駐/表示/有効無効/終了) |
| app/result_window.py | TypoChecker.App/ResultWindow.xaml | ✅ 移植(原文/生成並列・コピー・採用Y/N) |
| app/settings_window.py | TypoChecker.App/SettingsWindow.xaml | ✅ 移植(endpoint/model/temp/think/並列/上限/copy/Corpus) |
| app/backend.py | JobService.cs + TypoChecker.App/App.xaml.cs | ✅ コア＋WPF配線(ホットキー→生成→表示) |

## 移植ロードマップ

1. ✅ 純ロジック（Sanitizer/Prompts/OllamaClient/Models）＋テスト
2. ✅ AppSettings（JSON, System.Text.Json）/ CorpusStore ＋テスト
2.5 ✅ JobService（検証→プロンプト(+Corpus)→Ollama→サニタイズ、並列制限）＋テスト（IOllamaClientで注入可能）
3. ✅ グローバルホットキー（Win32 `RegisterHotKey`＋GetMessageループ）＝ TypoChecker.Daemon
4. ✅ 非破壊キャプチャ（SendInput Ctrl+C ＋ クリップボード退避/復元/反映待ち §7.2）
   ※ 3・4 はビルド＆クリップボード往復確認済み。実押下の動作確認は実機で。
5. 🟡 WPF GUI … ✅状態ウィンドウ＋結果ウィンドウ（原文/生成並列・コピー・採用Y/N）＋ホットキー配線。⏳設定画面/処理中インジケータ
6. 🟡 トレイ常駐 ✅（[X]で常駐・表示・有効/無効・終了）／ ⏳ 通知・履歴
7. ⏳ パッケージング（single-file publish, インストーラ）

## 設計メモ
- Core は GUI/OS非依存に保ち、ロジックはユニットテストで担保（プロトタイプのテスト資産を移植）。
- ホットキー＋非破壊キャプチャは AHK の役割を Win32 で再実装する（§14 の「作り直し」部分）。
- 思考モデル対策（think:false）と プロンプトv2 は Core に取り込み済み。
