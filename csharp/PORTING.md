# Phase 4: C#/.NET 移植（着手）

仕様 §14 / §15 Phase 4。プロトタイプ（AHK + Python）の挙動が固まったので、
本実装を C#/.NET へ移植する。**移植＝実質作り直し**（AHKロジックは流用不可前提）。

> 状態: **着手（土台のみ）**。純ロジック（Sanitizer / Prompts / OllamaClient / Models）を
> 移植し、CLI で動作確認できる構成まで。GUI(WPF)・ホットキー・トレイは未着手。

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
dotnet test TypoChecker.Tests/TypoChecker.Tests.csproj      # サニタイズ回帰
dotnet run --project TypoChecker.Cli -- typo "なおしたいテキスト"
echo 雑なメモ | dotnet run --project TypoChecker.Cli -- business
```

> この環境には .NET SDK が未導入のため未ビルド。SDK 導入後に上記で検証可能。

## Python → C# 対応表

| Python (プロトタイプ) | C# (本実装) | 状態 |
|---|---|---|
| app/sanitize.py | TypoChecker.Core/Sanitizer.cs | ✅ 移植 |
| app/prompts.py | TypoChecker.Core/Prompts.cs | ✅ 移植 |
| app/llm.py | TypoChecker.Core/OllamaClient.cs | ✅ 移植 |
| app/jobs.py | TypoChecker.Core/Models.cs (Job) | ✅ 移植 |
| app/config.py | TypoChecker.Core/AppSettings.cs | ⏳ 未 |
| app/corpus.py | TypoChecker.Core/CorpusStore.cs | ⏳ 未 |
| app/clipboard.py | Win32 Clipboard / System.Windows.Clipboard | ⏳ 未 |
| app/notify.py | Windows トースト（CommunityToolkit等） | ⏳ 未 |
| ahk/hotkeys.ahk | グローバルホットキー（RegisterHotKey/Win32） | ⏳ 未 |
| app/tray.py | NotifyIcon（WinForms相互運用 or Win32） | ⏳ 未 |
| app/result_window.py | WPF ResultWindow.xaml | ⏳ 未 |
| app/settings_window.py | WPF SettingsWindow.xaml | ⏳ 未 |
| app/backend.py | App + JobService（DispatcherでUIへ） | ⏳ 未 |

## 移植ロードマップ

1. ✅ 純ロジック（Sanitizer/Prompts/OllamaClient/Models）＋テスト
2. ⏳ AppSettings（JSON, System.Text.Json）/ CorpusStore
3. ⏳ グローバルホットキー（Win32 `RegisterHotKey` ＋ メッセージループ。AHK代替）
4. ⏳ 非破壊キャプチャ（SendInput Ctrl+C ＋ クリップボード退避/復元、§7.2 反映待ち）
5. ⏳ WPF GUI（結果ウィンドウ 原文/生成文 並列、設定画面、処理中インジケータ）
6. ⏳ トレイ常駐（NotifyIcon）/ 通知 / 履歴
7. ⏳ パッケージング（single-file publish, インストーラ）

## 設計メモ
- Core は GUI/OS非依存に保ち、ロジックはユニットテストで担保（プロトタイプのテスト資産を移植）。
- ホットキー＋非破壊キャプチャは AHK の役割を Win32 で再実装する（§14 の「作り直し」部分）。
- 思考モデル対策（think:false）と プロンプトv2 は Core に取り込み済み。
