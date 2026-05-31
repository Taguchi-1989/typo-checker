"""処理中インジケータ（画面上に「補正中…」を即時表示）。

ホットキー押下→生成完了までは数秒かかり、その間フィードバックが無いと不安なので、
ジョブ実行中だけ画面上部中央に小さな常時前面の表示を出す。アニメーションと
件数・経過秒は backend 側のタイマーが set_text() で更新する。
"""

import tkinter as tk


class ProcessingIndicator:
    def __init__(self, root):
        self.root = root
        self.win = None
        self.label = None

    def _alive(self):
        return self.win is not None and self.win.winfo_exists()

    def show(self):
        if self._alive():
            return
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)  # タイトルバー無しの小窓
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.95)
        except tk.TclError:
            pass

        frame = tk.Frame(self.win, bg="#1f6feb", padx=16, pady=8)
        frame.pack()
        self.label = tk.Label(frame, text="✍ 補正中…", fg="white", bg="#1f6feb",
                              font=("", 12, "bold"))
        self.label.pack()

        # 画面上部中央へ配置
        self.win.update_idletasks()
        w = self.win.winfo_width()
        sw = self.win.winfo_screenwidth()
        x = (sw - w) // 2
        self.win.geometry(f"+{x}+60")
        self.win.lift()

    def set_text(self, text):
        if self._alive() and self.label is not None:
            self.label.configure(text=text)

    def hide(self):
        if self._alive():
            self.win.destroy()
        self.win = None
        self.label = None
