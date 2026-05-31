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
from collections import deque
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
from app.tray import TrayIcon


class Backend:
    def __init__(self):
        self.settings = config.load_settings()
        self.corpus = CorpusStore()
        self._events = queue.Queue()
        self._running = 0                # 実行中ジョブ数
        self._pending = deque()          # 並列上限超過で待機中のジョブ（§Phase 3）
        self._result_windows = {}        # job_id -> ResultWindow（再表示用）
        # 履歴（メモリのみ・終了時破棄 §11.3）
        hist_max = self.settings["history"]["max_items"] if self.settings["history"]["enabled"] else 0
        self._history = deque(maxlen=hist_max or 1)

        self.root = tk.Tk()
        self.root.title("文章補正ツール")
        self._build_status_window()

        # 処理中インジケータ（画面上に「補正中…」を即時表示）
        self._indicator = ProcessingIndicator(self.root)
        self._anim_running = False
        self._anim_phase = 0
        self._busy_since = None

        # タスクトレイ常駐（§6.2 / Phase 3）
        self._enabled = True  # 無効化時は受信ジョブをスキップ
        self._tray = TrayIcon(
            tooltip=f"文章補正ツール: {self.settings['llm']['model']}",
            on_show=lambda: self._events.put(("tray_show", None)),
            on_toggle=lambda: self._events.put(("tray_toggle", None)),
            on_quit=lambda: self._events.put(("tray_quit", None)),
        )
        if self._tray.show():
            # トレイが使えるなら[X]はトレイへ最小化（常駐）
            self.root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

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
        ttk.Button(btns, text="履歴", command=self._open_history).pack(side="left", padx=6)
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
                elif kind == "tray_show":
                    self._show_window()
                elif kind == "tray_toggle":
                    self._toggle_enabled()
                elif kind == "tray_quit":
                    self._quit()
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def _handle_new(self, job):
        if not self._enabled:
            notify.notify("無効中", "補正ツールは無効化中です（トレイから有効化できます）")
            return
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
        # 並列上限まで実行、超過分はキュー待ち（§Phase 3）
        self._pending.append(job)
        self._start_indicator()  # 画面に「補正中…」を即時表示
        self._pump_jobs()

    def _pump_jobs(self):
        """並列上限の範囲でキューからジョブを実行へ移す。"""
        limit = max(1, int(self.settings["llm"].get("max_parallel", 2)))
        while self._pending and self._running < limit:
            job = self._pending.popleft()
            self._running += 1
            threading.Thread(target=self._run_llm, args=(job,),
                             name=f"tc-llm-{job.job_id}", daemon=True).start()
        self._update_jobs_label()

    def _update_jobs_label(self):
        waiting = len(self._pending)
        extra = f"（待機 {waiting}）" if waiting else ""
        self.lbl_jobs.configure(text=f"処理中ジョブ: {self._running}{extra}")

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
        self._running = max(0, self._running - 1)
        self._record_history(job)
        self._pump_jobs()  # 待機ジョブがあれば次を開始
        if self._running <= 0 and not self._pending:
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

    # --- 履歴（メモリのみ §11.3 / Phase 3） --------------------------------
    def _record_history(self, job):
        if self.settings["history"]["enabled"]:
            self._history.appendleft(job)

    def _open_history(self):
        if not self.settings["history"]["enabled"] or not self._history:
            messagebox.showinfo("履歴", "履歴はまだありません。", parent=self.root)
            return
        win = tk.Toplevel(self.root)
        win.title("履歴（メモリのみ・終了で破棄）")
        win.geometry("560x360")
        lb = tk.Listbox(win)
        lb.pack(fill="both", expand=True, padx=8, pady=8)
        jobs = list(self._history)
        for j in jobs:
            mark = {"done": "✓", "failed": "✗"}.get(j.status, "?")
            label = MODE_LABELS.get(j.mode, j.mode)
            snippet = (j.original_text or "").replace("\n", " ")[:30]
            lb.insert("end", f"{mark} [{j.created_at[11:19]}] {label}: {snippet}")

        def reopen(_=None):
            sel = lb.curselection()
            if sel:
                self._show_result_window(jobs[sel[0]])
        lb.bind("<Double-Button-1>", reopen)
        ttk.Button(win, text="選択した結果を再表示", command=reopen).pack(pady=(0, 8))

    # --- 処理中インジケータ -------------------------------------------------
    def _start_indicator(self):
        if self._anim_running:
            return
        self._anim_running = True
        self._busy_since = time.time()
        self._indicator.show()
        self._tick_indicator()

    def _tick_indicator(self):
        inflight = self._running + len(self._pending)
        if inflight <= 0:
            self._stop_indicator()
            return
        self._anim_phase = (self._anim_phase + 1) % 4
        dots = "." * self._anim_phase
        elapsed = int(time.time() - self._busy_since) if self._busy_since else 0
        count = f"  {inflight}件" if inflight > 1 else ""
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

    # --- トレイ常駐 -------------------------------------------------------
    def _hide_to_tray(self):
        """[X] で閉じてもトレイに常駐し続ける（§6.2）。

        トレイが利用不可になっていれば（復帰手段がないため）通常終了にフォールバック。
        """
        if not getattr(self._tray, "available", False):
            self._quit()
            return
        self.root.withdraw()
        notify.notify("常駐中", "タスクトレイに常駐しています（アイコンから表示/終了）")

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _toggle_enabled(self):
        self._enabled = not self._enabled
        if self._enabled:
            self._tray.set_enabled_label("無効にする")
            self._tray.set_tooltip(f"文章補正ツール: {self.settings['llm']['model']}")
            notify.notify("有効化", "補正ツールを有効にしました")
        else:
            self._tray.set_enabled_label("有効にする")
            self._tray.set_tooltip("文章補正ツール（無効中）")
            notify.notify("無効化", "補正ツールを無効にしました")

    def _quit(self):
        try:
            self._tray.stop()
        except Exception:  # noqa: BLE001
            pass
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
