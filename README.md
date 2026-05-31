# typo-checker — Windows常駐型ローカルLLM文章補正ツール

Windows上の**任意の入力欄で選択した文章**を、ホットキーひとつでローカルLLM（Ollama）に
渡して補正案を作り、**原文と並べて見比べてから自分で貼り付ける**常駐ツールです。

- 🔒 **ローカル完結** — 外部APIに一切送信しない（Ollama / localhost のみ）
- ✋ **非破壊** — 本文は書き換えない（Ctrl+Cで読むだけ）。貼り付けは人間が行う
- ⚡ **じゃまをしない** — 生成中も別作業OK。押した瞬間「✍ 補正中…」を画面表示
- 🧠 **使うほど寄る** — 採用した用例をfew-shotに差し込む Corpus（方式A）

> プロトタイプ（AHK v2 + Python + Ollama）。仕様は
> [requirements spec v0.2](local_llm_text_assistant_spec_v0.2.md) を参照。

---

## 2つのモード

| ショートカット | モード | 内容 |
|---|---|---|
| **Ctrl+Alt+T** | タイポ修正 | 誤字・脱字・誤変換・句読点の乱れだけを直す（文体は変えない） |
| **Ctrl+Alt+B** | ビジネス依頼文化 | 雑な口語を、意味を変えず相手に送れる依頼文へ整える |

選択 → ショートカット → 数秒で結果ウィンドウ（原文／生成文を並列表示）＋クリップボードへコピー
→ 元の場所で **Ctrl+V**。結果ウィンドウで「採用Y / 不採用N」を記録できます（意味保存判定）。

---

## 必要なもの

- Windows 10 / 11
- [Python](https://www.python.org/) 3.10+（tkinter同梱の通常版でOK / **追加pip依存なし**）
- [AutoHotkey v2](https://www.autohotkey.com/)
- [Ollama](https://ollama.com/) ＋ モデル
  ```
  ollama pull qwen3:8b
  ```
  既定は日本語が強い **qwen3:8b**。思考(thinking)は自動でオフにして高速化（typoで約6秒）。
  設定画面で他モデルにも切替できます（§8.2のRTX 3060/8GB候補を内蔵）。

## クイックスタート

```bash
# 1) Ollama を起動（アプリ or `ollama serve`）
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

設計上の特徴:
- クリップボードは **OSネイティブ(ctypes/Win32)** に直接書き込み、別アプリでの貼り付けを安定化
- AHK→バックエンドの本文は **UTF-8バイト列**で送信（日本語の文字化け回避）
- 思考モデル(Qwen3等)は `think:false` を送って高速化＋`<think>`除去で二重防御

---

## テスト（Ollama不要）

```
python tests\run_all.py
```

サニタイズ回帰 / 設定マージ / プロンプト・Corpus / HTTP往復 / OSクリップボード /
バックエンドのエラーパス（文字数超過・空選択・LLM失敗・採用ガード・コピー挙動）/
偽Ollamaを使ったGUI煙テスト までを、各テスト別プロセスで実行します。

---

## ロードマップ（仕様 §15）

- ✅ **Phase 0** … 品質検証ハーネス（[run_phase0.py](run_phase0.py)）で4モデル実測、レポート作成（`results/phase0_report.md`）。既定は qwen3:8b + think:false
- ✅ **Phase 1 MVP** … ホットキー2つ・非破壊取得・Ollama・サニタイズ・結果ウィンドウ・通知・採否Y/N
- ✅ **Phase 2** … 設定画面・モデル切替・Corpus（few-shot / 一括インポート）
- 🚧 **Phase 3（進行中）** … ✅タスクトレイ常駐 / ✅履歴(メモリ最大10) / ✅並列実行制限 / ⏳対象外アプリのガード
- 🔜 **Phase 4+** … C#/.NET移植、Corpus方式B(LoRA)

## プライバシー

選択文以外は取得しません。本文を永続ログに保存しません。外部送信なし。
Corpus は **ローカル保存のみ**（`corpus.json` はリポジトリに含めません）。

## ライセンス

[MIT](LICENSE)
