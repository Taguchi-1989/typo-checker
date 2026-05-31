"""常駐バックエンド（Phase 1 MVP + Phase 2）。

Tk を主スレッドで回し、HTTP 受け口（AHK連携）と LLM 呼び出しを別スレッドで動かす。
スレッド間はキューで受け渡し、クリップボード操作・ウィンドウ生成は必ず主スレッドで行う。

技術アーキテクチャ §13 対応:
  Hotkey Manager      -> ahk/hotkeys.ahk（外部）
  Clipboard Manager   -> AHK側で退避/取得/反映待ち/復元、結果コピーは本体（_set_clipboard）
  Job Queue           -> _events キュー（MVPは逐次1件相当）
  Prompt Router       -> prompts.build_prompt + Corpus
  Local LLM Client    -> llm.generate
  Output Sanitizer    -> sanitize.sanitize
  Result Window/Notifier/Settings -> 各モジュール
"""

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from app import clipboard, config, llm, notify
from app.corpus import CorpusStore
from app.jobs import Job, now_iso
from app.processing_indicator import ProcessingIndicator
from app.prompts import MODE_LABELS, build_prompt
from app.result_window import ResultWindow
from app.sanitize import sanitize
from app.server import start_server
from app.settings_window import SettingsWindow


class Backend:
    def __init__(self):
        self.settings = config.load_settings()
        self.corpus = CorpusStore()
        self._events = queue.Queue()
        self._active_jobs = 0
        self._result_windows = {}  # job_id -> ResultWindow（通知クリック前面化用）

        self.root = tk.Tk()
        self.root.title("文章補正ツール")
        self._build_status_window()

        # 処理中インジケータ（画面上に「補正中…」を即時表示）
        self._indicator = ProcessingIndicator(self.root)
        self._anim_running = False
        self._anim_phase = 0
        self._busy_since = None

        # HTTP 受け口（AHK からの POST /job）
        host = self.settings["server"]["host"]
        port = self.settings["server"]["port"]
        try:
            self.httpd, _ = start_server(host, port, self._on_job_from_http)
            self._set_server_label(f"待受: http://{host}:{port}")
        except OSError as e:
            messagebox.showerror(
                "起動エラー",
                f"ポート {port} を開けませんでした（多重起動 or 使用中）。\n{e}",
            )
            raise SystemExit(1)

        # 定期処理: イベント処理と接続状態の監視
        self.root.after(100, self._drain_events)
        self._check_connection_async()
        self.root.after(15000, self._periodic_conn_check)

    # --- ステータスウィンドウ（§6.2 最小: 接続状態表示） -------------------
    def _build_status_window(self):
        pad = {"padx": 12, "pady": 4}
        ttk.Label(self.root, text="ローカルLLM文章補正ツール", font=("", 12, "bold")).pack(**pad)

        info = ttk.Frame(self.root)
        info.pack(fill="x", **pad)
        self.lbl_model = ttk.Label(info, text="")
        self.lbl_model.pack(anchor="w")
        self.lbl_server = ttk.Label(info, text="")
        self.lbl_server.pack(anchor="w")
        self.lbl_conn = ttk.Label(info, text="接続状態: 確認中…")
        self.lbl_conn.pack(anchor="w")
        self.lbl_jobs = ttk.Label(info, text="処理中ジョブ: 0")
        self.lbl_jobs.pack(anchor="w")

        hk = self.settings["hotkeys"]
        ttk.Label(self.root, text=f"{hk['business']}: ビジネス依頼文化 / {hk['typo']}: タイポ修正",
                  foreground="#555").pack(**pad)

        btns = ttk.Frame(self.root)
        btns.pack(fill="x", **pad)
        ttk.Button(btns, text="設定", command=self._open_settings).pack(side="left")
        ttk.Button(btns, text="接続確認", command=self._check_connection_async).pack(side="left", padx=6)
        ttk.Button(btns, text="終了", command=self._quit).pack(side="right")

        self._refresh_labels()
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.geometry("420x220")

    def _refresh_labels(self):
        self.lbl_model.configure(text=f"モデル: {self.settings['llm']['model']}")

    def _set_server_label(self, text):
        self.lbl_server.configure(text=text)

    # --- HTTP からのジョブ投入（別スレッド） ------------------------------
    def _on_job_from_http(self, mode, text, source_app, window_title):
        job = Job(mode, text, source_app=source_app, window_title=window_title)
        self._events.put(("new", job))
        return job.job_id

    # --- 主スレッド: イベント処理 -----------------------------------------
    def _drain_events(self):
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "new":
                    self._handle_new(payload)
                elif kind == "done":
                    self._handle_done(payload)
                elif kind == "conn":
                    self._set_conn(payload)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def _handle_new(self, job):
        text = (job.original_text or "").strip()
        if not text:
            job.status = "failed"
            job.error_message = "選択範囲が空です"
            notify.notify("取得失敗", "文章を選択してから再実行してください")
            return
        if len(text) > self.settings["max_chars"]:
            job.status = "failed"
            job.error_message = "文字数超過"
            notify.notify("文字数超過",
                          f"{self.settings['max_chars']}字までです（{len(text)}字）")
            return
        # LLM 呼び出しを別スレッドで（生成中もユーザーは別作業可 §11.1）
        self._active_jobs += 1
        self.lbl_jobs.configure(text=f"処理中ジョブ: {self._active_jobs}")
        self._start_indicator()  # 画面に「補正中…」を即時表示
        threading.Thread(target=self._run_llm, args=(job,),
                         name=f"tc-llm-{job.job_id}", daemon=True).start()

    def _run_llm(self, job):
        s = self.settings
        job.status = "running"
        job.started_at = now_iso()
        try:
            fewshot = None
            if s["corpus"]["enabled"]:
                fewshot = self.corpus.select_fewshot(job.mode, s["corpus"]["fewshot_count"])
            instructions = {m: (s["prompts"].get(m) or None) for m in ("business", "typo")}
            instructions = {k: v for k, v in instructions.items() if v}
            prompt = build_prompt(job.mode, job.original_text,
                                  instructions=instructions or None, fewshot=fewshot)
            raw = llm.generate(
                s["llm"]["endpoint"], s["llm"]["model"], prompt,
                s["llm"]["temperature"][job.mode], timeout=s["llm"]["timeout_sec"],
                think=s["llm"].get("think"),
            )
            job.result_text = sanitize(
                raw,
                strip_preamble=s["sanitize"]["strip_preamble"],
                strip_wrapping_quotes=s["sanitize"]["strip_wrapping_quotes"],
                preserve_linebreaks=s["sanitize"]["preserve_linebreaks"],
            )
            job.sanitized = True
            job.status = "done"
        except llm.LLMError as e:
            job.status = "failed"
            job.error_message = str(e)
        except Exception as e:  # noqa: BLE001
            job.status = "failed"
            job.error_message = f"想定外のエラー: {e}"
        finally:
            job.completed_at = now_iso()
            self._events.put(("done", job))

    def _handle_done(self, job):
        self._active_jobs = max(0, self._active_jobs - 1)
        self.lbl_jobs.configure(text=f"処理中ジョブ: {self._active_jobs}")
        if self._active_jobs <= 0:
            self._stop_indicator()
        label = MODE_LABELS.get(job.mode, job.mode)

        if job.status == "failed":
            notify.notify("生成失敗", job.error_message or "生成に失敗しました")
            self._show_result_window(job)  # 失敗内容も結果ウィンドウに表示（§10）
            return

        copied = False
        if self.settings["clipboard"]["copy_result_on_complete"]:
            self._set_clipboard(job.result_text or "")
            copied = True

        win = self._show_result_window(job)
        if win and copied:
            win.set_copied_notice()

        msg = f"{label}の生成が完了しました。"
        if copied:
            msg += "結果をクリップボードにコピーしました。"
        notify.notify("補正完了", msg)

    def _show_result_window(self, job):
        if job.status == "failed":
            # 失敗は簡易表示（原文 + エラー）
            job.result_text = f"[生成失敗] {job.error_message}"
        win = ResultWindow(self.root, job, on_copy=self._set_clipboard,
                           on_accept=self._on_accept)
        self._result_windows[job.job_id] = win
        return win

    # --- 処理中インジケータ -------------------------------------------------
    def _start_indicator(self):
        if self._anim_running:
            return
        self._anim_running = True
        self._busy_since = time.time()
        self._indicator.show()
        self._tick_indicator()

    def _tick_indicator(self):
        if self._active_jobs <= 0:
            self._stop_indicator()
            return
        self._anim_phase = (self._anim_phase + 1) % 4
        dots = "." * self._anim_phase
        elapsed = int(time.time() - self._busy_since) if self._busy_since else 0
        n = self._active_jobs
        count = f"  {n}件" if n > 1 else ""
        self._indicator.set_text(f"✍ 補正中{dots:<3}{count}   {elapsed}秒")
        self.root.after(300, self._tick_indicator)

    def _stop_indicator(self):
        self._anim_running = False
        self._busy_since = None
        self._indicator.hide()

    # --- 採否記録（§18.3 意味保存 Y/N） -----------------------------------
    def _on_accept(self, job, accepted, final_text):
        job.accepted = accepted
        # 失敗ジョブや空文をCorpusへ取り込まない（誤学習防止）
        if (accepted and self.settings["corpus"]["enabled"]
                and job.status == "done" and (final_text or "").strip()):
            self.corpus.add(job.mode, job.original_text, final_text, now_iso(),
                            max_items=self.settings["corpus"]["max_items"])

    # --- クリップボード -----------------------------------------------------
    def _set_clipboard(self, text):
        """OS クリップボードへ直接書き込む（Tk非依存で貼り付けを安定化）。

        ctypes 実装が失敗した場合のみ Tk へフォールバックする。
        """
        if clipboard.set_clipboard_text(text or ""):
            return
        # フォールバック（非Windows等）
        self.root.clipboard_clear()
        if text:
            self.root.clipboard_append(text)
        self.root.update_idletasks()

    # --- 接続監視 ---------------------------------------------------------
    def _check_connection_async(self):
        def worker():
            ok = llm.check_connection(self.settings["llm"]["endpoint"], timeout=4)
            self._events.put(("conn", ok))
        threading.Thread(target=worker, name="tc-conn", daemon=True).start()

    def _periodic_conn_check(self):
        self._check_connection_async()
        self.root.after(15000, self._periodic_conn_check)

    def _set_conn(self, ok):
        if ok:
            self.lbl_conn.configure(text="接続状態: 接続OK", foreground="green")
        else:
            self.lbl_conn.configure(text="接続状態: 未接続（Ollama未起動?）", foreground="red")

    # --- 設定 -------------------------------------------------------------
    def _open_settings(self):
        SettingsWindow(self.root, self.settings, self.corpus, on_save=self._apply_settings)

    def _apply_settings(self, new_settings):
        old_server = self.settings["server"]
        self.settings = new_settings
        config.save_settings(new_settings)
        self._refresh_labels()
        self._check_connection_async()
        if new_settings["server"] != old_server:
            messagebox.showinfo("設定", "待受ホスト/ポートの変更は再起動後に反映されます。")

    def _quit(self):
        try:
            self.httpd.shutdown()
        except Exception:  # noqa: BLE001
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    Backend().run()


if __name__ == "__main__":
    main()
