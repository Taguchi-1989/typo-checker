"""結果ウィンドウ（§6.1 MVP必須）。

原文ペイン／生成文ペインを並列表示。コピー再実行・採用Y/N(§18.3)・閉じる。
本文自動挿入ボタンは置かない（§6.1 誤爆回避）。生成文ペインは編集可能で、
編集後の最終文をコピー／採用できる（§9.1 採用フロー）。
"""

import tkinter as tk
from tkinter import ttk

from app.prompts import MODE_LABELS


class ResultWindow:
    def __init__(self, root, job, on_copy, on_accept):
        """
        Args:
            root: Tk ルート
            job: Job インスタンス
            on_copy: callable(text) -> None   生成文をクリップボードへ
            on_accept: callable(job, accepted: bool, final_text: str) -> None
        """
        self.job = job
        self.on_copy = on_copy
        self.on_accept = on_accept

        self.win = tk.Toplevel(root)
        self.win.title(f"補正結果 - {MODE_LABELS.get(job.mode, job.mode)}")
        self.win.geometry("860x520")
        self.win.minsize(640, 380)

        self._build()
        self.win.lift()
        self.win.attributes("-topmost", True)
        self.win.after(400, lambda: self.win.attributes("-topmost", False))
        self.win.focus_force()

    def _build(self):
        job = self.job
        pad = {"padx": 10, "pady": 6}

        header = ttk.Frame(self.win)
        header.pack(fill="x", **pad)
        ttk.Label(
            header,
            text=f"モード: {MODE_LABELS.get(job.mode, job.mode)}",
            font=("", 11, "bold"),
        ).pack(side="left")
        ttk.Label(header, text=f"作成: {job.created_at}").pack(side="right")

        panes = ttk.Frame(self.win)
        panes.pack(fill="both", expand=True, padx=10)
        panes.columnconfigure(0, weight=1)
        panes.columnconfigure(1, weight=1)
        panes.rowconfigure(1, weight=1)

        ttk.Label(panes, text="原文").grid(row=0, column=0, sticky="w")
        ttk.Label(panes, text="生成文（編集可）").grid(row=0, column=1, sticky="w")

        self.src = tk.Text(panes, wrap="word", height=12)
        self.src.insert("1.0", job.original_text)
        self.src.configure(state="disabled", background="#f4f4f4")
        self.src.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=4)

        self.gen = tk.Text(panes, wrap="word", height=12)
        self.gen.insert("1.0", job.result_text or "")
        self.gen.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=4)

        self.status = ttk.Label(self.win, text="")
        self.status.pack(fill="x", padx=10)

        btns = ttk.Frame(self.win)
        btns.pack(fill="x", padx=10, pady=10)
        ttk.Button(btns, text="コピー（生成結果を再コピー）", command=self._copy).pack(side="left")
        ttk.Button(btns, text="採用 Y（意味一致）", command=lambda: self._accept(True)).pack(side="left", padx=6)
        ttk.Button(btns, text="不採用 N", command=lambda: self._accept(False)).pack(side="left")
        ttk.Button(btns, text="閉じる", command=self.win.destroy).pack(side="right")

    def _current_text(self):
        return self.gen.get("1.0", "end-1c")

    def _copy(self):
        self.on_copy(self._current_text())
        self.status.configure(text="生成結果をクリップボードにコピーしました。")

    def _accept(self, accepted):
        self.on_accept(self.job, accepted, self._current_text())
        mark = "採用(Y)" if accepted else "不採用(N)"
        self.status.configure(text=f"意味保存判定を記録しました: {mark}")

    def set_copied_notice(self):
        """完了時に自動コピーした旨を表示（§7.3 上書き明示）。"""
        self.status.configure(text="生成結果をクリップボードにコピー済みです。")

    def raise_window(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()

    def close(self):
        """ウィンドウを破棄する（次の補正指示で前回分を閉じる用）。多重呼び出し安全。"""
        try:
            self.win.destroy()
        except Exception:  # noqa: BLE001
            pass
