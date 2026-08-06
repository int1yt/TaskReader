"""聊天面板：与桌宠直接对话，自动分解任务。"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from task_reader.engine import TaskReader
from app.config import load_config, LANG_STRINGS


class ChatPanel:
    def __init__(self, master=None, on_tasks_extracted=None, on_close=None):
        self._cfg = load_config()
        self._reader = TaskReader()
        self._on_tasks_extracted = on_tasks_extracted
        self._on_close = on_close
        self._lang = self._cfg.get("language", {}).get("ui_lang", "zh")
        self._strings = LANG_STRINGS.get(self._lang, LANG_STRINGS["zh"])

        self.win = tk.Toplevel(master) if master else tk.Tk()
        self.win.title(self._strings["chat"])
        self.win.geometry("420x520")
        self.win.protocol("WM_DELETE_WINDOW", self._hide)
        try:
            self.win.iconbitmap(default="")
        except Exception:
            pass

        self._build()

    def _t(self, key):
        self._strings = LANG_STRINGS.get(self._lang, LANG_STRINGS["zh"])
        return self._strings.get(key, key)

    def _hide(self):
        self.win.withdraw()
        if self._on_close:
            self._on_close()

    def show(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()

    def _build(self):
        profile = self._cfg.get("bot_profile", {})
        name = profile.get("name", "小读")

        # 聊天历史
        self._chat_area = scrolledtext.ScrolledText(
            self.win, wrap=tk.WORD, state=tk.DISABLED,
            font=("Microsoft YaHei", 10),
            bg="#F5F5DC", fg="#333",
        )
        self._chat_area.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 0))
        self._chat_area.tag_config("user", foreground="#0066CC", font=("Microsoft YaHei", 10, "bold"))
        self._chat_area.tag_config("bot", foreground="#228B22", font=("Microsoft YaHei", 10))
        self._chat_area.tag_config("task", foreground="#FF8C00", font=("Microsoft YaHei", 10))
        self._chat_area.tag_config("time", foreground="#888", font=("Microsoft YaHei", 9))

        # 输入框
        input_frame = ttk.Frame(self.win, padding=6)
        input_frame.pack(fill=tk.X)

        self._input = ttk.Entry(input_frame, font=("Microsoft YaHei", 10))
        self._input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self._input.bind("<Return>", lambda e: self._send())
        self._input.focus_set()

        send_btn = ttk.Button(input_frame, text="发送", command=self._send, width=6)
        send_btn.pack(side=tk.RIGHT)

        self._add_bot_msg(f"你好！我是 {name}，告诉我你要做什么，我帮你分解任务~")

    def _add_user_msg(self, text: str):
        self._append(f"你：{text}\n", "user")

    def _add_bot_msg(self, text: str):
        self._append(f"{self._cfg.get('bot_profile', {}).get('name', '小读')}：{text}\n", "bot")

    def _add_task_msg(self, text: str):
        self._append(text + "\n", "task")

    def _append(self, text: str, tag: str):
        self._chat_area.config(state=tk.NORMAL)
        self._chat_area.insert(tk.END, text, tag)
        self._chat_area.see(tk.END)
        self._chat_area.config(state=tk.DISABLED)

    def _format_task(self, t: dict, index: int) -> str:
        name = t.get("task") or t.get("raw") or "未命名任务"
        time_str = t.get("time") or ""
        time_text = t.get("time_text") or ""
        if time_str and time_text:
            time_disp = f"{time_str}（{time_text}）"
        elif time_str:
            time_disp = time_str
        else:
            time_disp = "未指定时间"
        place = t.get("place") or ""
        notes = t.get("notes") or ""
        extra = f" | {place}" if place else ""
        extra += f" | {notes}" if notes else ""
        return f"  {index}. {name}\n     时间：{time_disp}{extra}"

    def _send(self):
        text = self._input.get().strip()
        if not text:
            return
        self._input.delete(0, tk.END)
        self._add_user_msg(text)

        # 解析任务
        use_llm = self._cfg.get("model", {}).get("use_llm", False)
        try:
            tasks = self._reader.parse_json(text, use_llm=use_llm)
        except Exception:
            self._add_bot_msg("抱歉，处理时出错了，请稍后再试。")
            return

        if not tasks:
            self._add_bot_msg(self._cfg.get("reply_style", {}).get("no_task",
                               "没有识别到任务，换个说法试试？"))
            return

        # 显示任务
        style = self._cfg.get("reply_style", {})
        header = style.get("task_header", "收到！为你整理了 {count} 个任务：")
        self._add_bot_msg(header.format(count=len(tasks)))

        for i, t in enumerate(tasks, 1):
            self._add_task_msg(self._format_task(t, i))

        footer = style.get("task_footer", "")
        if footer:
            self._add_bot_msg(footer)

        if self._on_tasks_extracted:
            self._on_tasks_extracted(tasks)

    def refresh_config(self):
        self._cfg = load_config()
        self._lang = self._cfg.get("language", {}).get("ui_lang", "zh")
        self._strings = LANG_STRINGS.get(self._lang, LANG_STRINGS["zh"])
        self.win.title(self._t("chat"))
