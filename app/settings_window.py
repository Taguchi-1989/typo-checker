"""設定画面（Phase 2 / §16）。

タブ: 一般（エンドポイント・モデル選択・temperature・コピー挙動・上限）
      プロンプト（モード別の指示文編集 §8.4）
      Corpus（有効化・件数・一括インポート・一覧/削除 §9）

ホットキーは AHK 側が所有するため、ここでは表示のみ（変更は ahk/hotkeys.ahk）。
"""

import copy
import tkinter as tk
from tkinter import messagebox, ttk

from app import llm
from app.config import MODEL_CANDIDATES
from app.jobs import now_iso
from app.prompts import DEFAULT_INSTRUCTIONS, MODE_LABELS


class SettingsWindow:
    def __init__(self, root, settings, corpus, on_save):
        """
        Args:
            settings: 現在の設定 dict（編集対象のコピーを取る）
            corpus: CorpusStore
            on_save: callable(new_settings) -> None  保存と適用
        """
        self.corpus = corpus
        self.on_save = on_save
        self.s = copy.deepcopy(settings)

        self.win = tk.Toplevel(root)
        self.win.title("設定")
        self.win.geometry("720x600")
        self.win.minsize(600, 480)

        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self._build_general(nb)
        self._build_prompts(nb)
        self._build_corpus(nb)

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(bar, text="保存して適用", command=self._save).pack(side="right")
        ttk.Button(bar, text="閉じる", command=self.win.destroy).pack(side="right", padx=6)

    # --- 一般タブ ---------------------------------------------------------
    def _build_general(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="一般")
        f.columnconfigure(1, weight=1)
        row = 0

        ttk.Label(f, text="ホットキー（AHK側で固定 / 変更は hotkeys.ahk）").grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 0))
        row += 1
        hk = self.s["hotkeys"]
        ttk.Label(f, text=f"  ビジネス: {hk['business']}    タイポ: {hk['typo']}").grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8)
        row += 1

        ttk.Separator(f).grid(row=row, column=0, columnspan=3, sticky="ew", pady=8)
        row += 1

        ttk.Label(f, text="Ollama エンドポイント").grid(row=row, column=0, sticky="w", padx=8, pady=4)
        self.var_endpoint = tk.StringVar(value=self.s["llm"]["endpoint"])
        ttk.Entry(f, textvariable=self.var_endpoint).grid(row=row, column=1, columnspan=2, sticky="ew", padx=8)
        row += 1

        ttk.Label(f, text="モデル").grid(row=row, column=0, sticky="w", padx=8, pady=4)
        self.var_model = tk.StringVar(value=self.s["llm"]["model"])
        self.model_cb = ttk.Combobox(f, textvariable=self.var_model, values=MODEL_CANDIDATES)
        self.model_cb.grid(row=row, column=1, sticky="ew", padx=8)
        ttk.Button(f, text="一覧取得/接続テスト", command=self._fetch_models).grid(row=row, column=2, padx=8)
        row += 1

        self.conn_label = ttk.Label(f, text="")
        self.conn_label.grid(row=row, column=1, columnspan=2, sticky="w", padx=8)
        row += 1

        ttk.Label(f, text="temperature（business）").grid(row=row, column=0, sticky="w", padx=8, pady=4)
        self.var_tb = tk.StringVar(value=str(self.s["llm"]["temperature"]["business"]))
        ttk.Entry(f, textvariable=self.var_tb, width=8).grid(row=row, column=1, sticky="w", padx=8)
        row += 1
        ttk.Label(f, text="temperature（typo）").grid(row=row, column=0, sticky="w", padx=8, pady=4)
        self.var_tt = tk.StringVar(value=str(self.s["llm"]["temperature"]["typo"]))
        ttk.Entry(f, textvariable=self.var_tt, width=8).grid(row=row, column=1, sticky="w", padx=8)
        row += 1

        self.var_copy = tk.BooleanVar(value=self.s["clipboard"]["copy_result_on_complete"])
        ttk.Checkbutton(f, text="完了時に自動でクリップボードへコピー（OFFでコピーボタン押下時のみ）",
                        variable=self.var_copy).grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=4)
        row += 1

        ttk.Label(f, text="最大文字数").grid(row=row, column=0, sticky="w", padx=8, pady=4)
        self.var_maxchars = tk.StringVar(value=str(self.s["max_chars"]))
        ttk.Entry(f, textvariable=self.var_maxchars, width=8).grid(row=row, column=1, sticky="w", padx=8)
        row += 1

    def _fetch_models(self):
        ep = self.var_endpoint.get().strip()
        try:
            models = llm.list_models(ep)
            if models:
                self.model_cb.configure(values=models)
                self.conn_label.configure(text=f"接続OK / {len(models)}モデル検出", foreground="green")
            else:
                self.conn_label.configure(text="接続OK（モデル未pull）", foreground="orange")
        except llm.LLMError as e:
            self.conn_label.configure(text=str(e), foreground="red")

    # --- プロンプトタブ ---------------------------------------------------
    def _build_prompts(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="プロンプト")
        self.prompt_texts = {}
        for i, mode in enumerate(("business", "typo")):
            ttk.Label(f, text=f"{MODE_LABELS[mode]} の指示文（空欄で既定に戻す）").pack(
                anchor="w", padx=8, pady=(8, 0))
            txt = tk.Text(f, wrap="word", height=10)
            current = self.s["prompts"].get(mode) or DEFAULT_INSTRUCTIONS[mode]
            txt.insert("1.0", current)
            txt.pack(fill="both", expand=True, padx=8, pady=4)
            self.prompt_texts[mode] = txt
        ttk.Label(f, text="※ 入力文は自動で末尾に付加されます。出力は本文のみを指示してください。").pack(
            anchor="w", padx=8, pady=(0, 8))

    # --- Corpus タブ ------------------------------------------------------
    def _build_corpus(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="Corpus")

        c = self.s["corpus"]
        top = ttk.Frame(f)
        top.pack(fill="x", padx=8, pady=8)
        self.var_corpus_enabled = tk.BooleanVar(value=c["enabled"])
        ttk.Checkbutton(top, text="Corpus（few-shot注入）を有効化", variable=self.var_corpus_enabled).pack(side="left")
        ttk.Label(top, text="  注入件数").pack(side="left", padx=(12, 2))
        self.var_fewshot = tk.StringVar(value=str(c["fewshot_count"]))
        ttk.Entry(top, textvariable=self.var_fewshot, width=5).pack(side="left")
        ttk.Label(top, text="  最大保持件数").pack(side="left", padx=(12, 2))
        self.var_maxitems = tk.StringVar(value=str(c["max_items"]))
        ttk.Entry(top, textvariable=self.var_maxitems, width=6).pack(side="left")

        # 一括インポート
        imp = ttk.LabelFrame(f, text="一括インポート（空行区切りで複数の良い文例を取り込み）")
        imp.pack(fill="x", padx=8, pady=4)
        self.var_import_mode = tk.StringVar(value="business")
        ttk.Radiobutton(imp, text="ビジネス", variable=self.var_import_mode, value="business").pack(side="left", padx=4)
        ttk.Radiobutton(imp, text="タイポ", variable=self.var_import_mode, value="typo").pack(side="left", padx=4)
        ttk.Button(imp, text="取り込む", command=self._import).pack(side="right", padx=4)
        self.import_text = tk.Text(f, wrap="word", height=5)
        self.import_text.pack(fill="x", padx=8, pady=4)

        # 一覧
        ttk.Label(f, text="登録済み用例").pack(anchor="w", padx=8)
        listfr = ttk.Frame(f)
        listfr.pack(fill="both", expand=True, padx=8, pady=4)
        self.tree = ttk.Treeview(listfr, columns=("mode", "src", "acc"), show="headings", height=8)
        self.tree.heading("mode", text="mode")
        self.tree.heading("src", text="原文")
        self.tree.heading("acc", text="確定文/文例")
        self.tree.column("mode", width=70, anchor="center")
        self.tree.column("src", width=240)
        self.tree.column("acc", width=240)
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(listfr, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)
        ttk.Button(f, text="選択した用例を削除", command=self._delete_selected).pack(anchor="e", padx=8, pady=4)
        self._refresh_tree()

    def _refresh_tree(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for it in self.corpus.list():
            self.tree.insert("", "end", iid=it["id"],
                             values=(it.get("mode"),
                                     (it.get("source_text") or "")[:40],
                                     (it.get("accepted_text") or "")[:40]))

    def _import(self):
        blob = self.import_text.get("1.0", "end-1c").strip()
        if not blob:
            return
        added = self.corpus.import_bulk(self.var_import_mode.get(), blob, now_iso(),
                                        max_items=self._int(self.var_maxitems, 200))
        self.import_text.delete("1.0", "end")
        self._refresh_tree()
        messagebox.showinfo("インポート", f"{added}件を取り込みました。", parent=self.win)

    def _delete_selected(self):
        for iid in self.tree.selection():
            self.corpus.delete(iid)
        self._refresh_tree()

    # --- 保存 -------------------------------------------------------------
    @staticmethod
    def _int(var, default):
        try:
            return int(float(var.get()))
        except (ValueError, tk.TclError):
            return default

    @staticmethod
    def _float(var, default):
        try:
            return float(var.get())
        except (ValueError, tk.TclError):
            return default

    def _save(self):
        s = self.s
        s["llm"]["endpoint"] = self.var_endpoint.get().strip()
        s["llm"]["model"] = self.var_model.get().strip()
        s["llm"]["temperature"]["business"] = self._float(self.var_tb, 0.4)
        s["llm"]["temperature"]["typo"] = self._float(self.var_tt, 0.2)
        s["clipboard"]["copy_result_on_complete"] = bool(self.var_copy.get())
        s["max_chars"] = self._int(self.var_maxchars, 3000)

        for mode, txt in self.prompt_texts.items():
            val = txt.get("1.0", "end-1c").strip()
            # 既定と同一なら空に戻す（既定追従のため）
            s["prompts"][mode] = "" if val == DEFAULT_INSTRUCTIONS[mode] else val

        s["corpus"]["enabled"] = bool(self.var_corpus_enabled.get())
        s["corpus"]["fewshot_count"] = self._int(self.var_fewshot, 3)
        s["corpus"]["max_items"] = self._int(self.var_maxitems, 200)

        self.on_save(copy.deepcopy(s))
        messagebox.showinfo("設定", "保存しました。", parent=self.win)
        self.win.destroy()
