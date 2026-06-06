# typo-checker — Windows常駐型ローカルLLM文章補正ツール

> *A Windows tray app that proofreads / rewrites selected text with a local LLM (Ollama). Non-destructive, fully offline, Japanese-focused.*

![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)
![LLM](https://img.shields.io/badge/LLM-Ollama%20(local)-111111)
![License](https://img.shields.io/badge/license-MIT-green)

Windows上の**任意の入力欄で選択した文章**を、ホットキーひとつでローカルLLM（Ollama）に
渡して補正案を作り、**原文と並べて見比べてから自分で貼り付ける**常駐ツールです。

- 🔒 **ローカル完結** — 外部APIに一切送信しない（Ollama / 127.0.0.1 のみ）
- ✋ **非破壊** — 本文は書き換えない（Ctrl+Cで読むだけ）。貼り付けは人間が行う
- ⚡ **じゃまをしない** — 生成中も別作業OK。押した瞬間「✍ 補正中…」を画面表示
- 🪟 **画面に溜めない** — 次の補正を始めると前回の結果ウィンドウは自動で閉じる
- 🧠 **使うほど寄る** — 採用した用例をfew-shotに差し込む Corpus（方式A）

> プロトタイプ（AutoHotkey v2 + Python + Ollama）。仕様は
> [requirements spec v0.2](local_llm_text_assistant_spec_v0.2.md) を参照。

---

## 2つのモード

| ショートカット | モード | 内容 |
|---|---|---|
| **Ctrl+Alt+T** | タイポ修正 | 誤字・脱字・誤変換・句読点の乱れだけを直す（文体は変えない） |
| **Ctrl+Alt+B** | ビジネス依頼文化 | 雑な口語を、意味を変えず相手に送れる依頼文へ整える |

選択 → ショートカット → 数秒で結果ウィンドウ（原文／生成文を並列表示）＋クリップボードへコピー
→ 元の場所で **Ctrl+V**。結果ウィンドウで「採用Y / 不採用N」を記録できます（意味保存判定）。

**例（タイポ修正）**

```
入力: おせわになっておりまs。先日のけんで、しりょうをそうふいたしますのでごかくにんお願いします。
出力: お世話になっております。先日の会議で、資料をお送りいたしますので、ご確認のほどお願いします。
```

---

## 必要なもの

- Windows 10 / 11
- [Python](https://www.python.org/) 3.10+（tkinter同梱の通常版でOK / **追加pip依存なし**）
- [AutoHotkey v2](https://www.autohotkey.com/)
- [Ollama](https://ollama.com/) ＋ モデル（下記）
- GPU: **NVIDIA RTX 3060 / VRAM 6GB** を基準に最適化（CPU実行も可能だが遅い）

### モデルの用意（既定: 日本語特化 Qwen3.5-4B）

既定モデルは **`qwen3.5-jp-4b:q6`**
（[dahara1氏](https://huggingface.co/dahara1/Qwen3.5-4B-UD-japanese-imatrix) の日本語特化
Qwen3.5-4B imatrix・Q6_K, 約3.8GB）。6GBに**100% GPU常駐**し、thinkingを切って
**warm 約1秒**で補正します。

```bash
# 1) ベースGGUFを取得
ollama pull hf.co/dahara1/Qwen3.5-4B-UD-japanese-imatrix:Q6_K
# 2) 同梱Modelfileで作成（settings.json の既定名 qwen3.5-jp-4b:q6 と一致）
ollama create qwen3.5-jp-4b:q6 -f models/qwen3.5-jp-4b.Modelfile
```

> ⚠️ **Modelfileは必須です。** HFのGGUFを `ollama pull/cp` で直接使うと、Ollama(0.30系)が
> Qwen3.5のチャット書式（`RENDERER`/`PARSER qwen3.5`）を付与できず素通しテンプレートになり、
> 停止トークンが効かず思考が止まらずコンテキスト上限まで暴走します（**1補正に約1分**）。
> 同梱の [models/qwen3.5-jp-4b.Modelfile](models/qwen3.5-jp-4b.Modelfile) で作成すると
> 正常化します（warm 約1秒）。理由はファイル冒頭のコメント参照。

設定画面から他モデルにも切替できます（6GB向けに `qwen3.5:4b` / `qwen3.5:2b` / `gemma4:e2b`
等を内蔵候補に用意）。**8B級は6GBではVRAM超過→CPUオフロードで生成が遅くなる**ため非推奨です。

## クイックスタート

```bash
# 1) Ollama を起動（アプリ or `ollama serve`）し、上記でモデルを作成
# 2) バックエンドを起動
python run_app.py
# 3) ahk/hotkeys.ahk をダブルクリックで常駐
# 4) どこかで文章を選択 → Ctrl+Alt+T / Ctrl+Alt+B
```

Windows なら **`start.bat`** をダブルクリックすれば 2〜3 をまとめて起動できます。
常駐・自動起動の設定は [使い方.md](使い方.md) を参照。

---

## 仕組み（アーキテクチャ）

```
[選択文] -Ctrl+C(非破壊)-> [AHK: 反映待ち+復元] -HTTP/job-> [Python常駐バックエンド]
   -> Prompt(+Corpus few-shot) -> Ollama -> サニタイズ
   -> クリップボード + 結果ウィンドウ(原文/生成文) + 通知 -> [人間がCtrl+Vで貼る]
```

| 構成 | ファイル |
|---|---|
| ホットキー & 非破壊キャプチャ（AHK v2） | [ahk/hotkeys.ahk](ahk/hotkeys.ahk) |
| 常駐バックエンド（Tk + HTTP受け口 + ジョブ管理） | [app/backend.py](app/backend.py) |
| Ollama クライアント（thinking制御対応） | [app/llm.py](app/llm.py) |
| プロンプト + Corpus few-shot注入 | [app/prompts.py](app/prompts.py) |
| 出力サニタイズ（前置き/引用符/フェンス/`<think>`除去・改行保持） | [app/sanitize.py](app/sanitize.py) |
| 用例コーパス（方式A） | [app/corpus.py](app/corpus.py) |
| 結果ウィンドウ / 設定画面 / 処理中表示 / 通知 / OSクリップボード | app/ 各モジュール |
| 既定モデルのOllama定義 | [models/qwen3.5-jp-4b.Modelfile](models/qwen3.5-jp-4b.Modelfile) |

設計上の特徴:
- クリップボードは **OSネイティブ(ctypes/Win32)** に直接書き込み、別アプリでの貼り付けを安定化
- AHK→バックエンドの本文は **UTF-8バイト列**で送信（日本語の文字化け回避）
- 思考モデル(Qwen3.5等)は `think:false` を送って高速化＋`<think>`除去で二重防御
- Ollamaの接続先は **`127.0.0.1`**（Windowsで `localhost` が IPv6`::1` に解決され接続拒否になるのを回避）

---

## テスト（Ollama不要）

```bash
python tests/run_all.py
```

サニタイズ回帰 / 設定マージ / プロンプト・Corpus / HTTP往復 / OSクリップボード /
バックエンドのエラーパス（文字数超過・空選択・LLM失敗・採用ガード・コピー挙動）/
偽Ollamaを使ったGUI煙テスト までを、各テスト別プロセスで実行します。

---

## ロードマップ（仕様 §15）

- ✅ **Phase 0** … 品質検証ハーネス（[run_phase0.py](run_phase0.py)）で複数モデルを実測・比較（`results/phase0_report.md`）
- ✅ **Phase 1 MVP** … ホットキー2つ・非破壊取得・Ollama・サニタイズ・結果ウィンドウ・通知・採否Y/N
- ✅ **Phase 2** … 設定画面・モデル切替・Corpus（few-shot / 一括インポート）
- ✅ **Phase 3** … タスクトレイ常駐 / 履歴(メモリ最大10) / 並列実行制限 / パスワード欄ガード
- 🚧 **Phase 4（進行中）** … C#/.NET移植。純ロジック（Sanitizer/Prompts/OllamaClient/JobService）と
  WPF GUI・トレイ・設定・履歴を実装（[csharp/](csharp/PORTING.md)）
- 🔜 **Phase 5** … Corpus方式B(LoRA) ほか

> 既定モデルは当初 `qwen3:8b` でしたが、RTX 3060 6GB 実機に合わせて
> 日本語特化 `qwen3.5-jp-4b:q6`（4B・6GB常駐）へ移行しました。

---

## プライバシー

選択文以外は取得しません。本文を永続ログに保存しません。外部送信なし。
`settings.json` と Corpus（`corpus.json`）は **ローカル保存のみ**でリポジトリに含めません（`.gitignore` 済み）。

## ライセンス

[MIT](LICENSE)
