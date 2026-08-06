"""任务清单面板：展示所有识别出的任务，支持勾选完成。"""
from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime, date

from .config import load_config, save_config, LANG_STRINGS

TASKS_FILE = Path(os.environ.get("TASKREADER_CONFIG",
                 Path.home() / ".taskreader")) / "tasks.json"


class TaskPanel:
    def __init__(self, master=None, on_close=None):
        self._cfg = load_config()
        self._on_close = on_close
        self._lang = self._cfg.get("language", {}).get("ui_lang", "zh")
        self._strings = LANG_STRINGS.get(self._lang, LANG_STRINGS["zh"])
        self._tasks = []
        self._check_vars = {}

        self.win = tk.Toplevel(master) if master else tk.Tk()
        self.win.title(self._t("task_list"))
        self.win.geometry("550x500")
        self.win.protocol("WM_DELETE_WINDOW", self._hide)
        try:
            self.win.iconbitmap(default="")
        except Exception:
            pass

        self._build()
        self._load_tasks()

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
        # 顶部工具栏
        toolbar = ttk.Frame(self.win, padding=4)
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="清空已完成", command=self._clear_done).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="清空全部", command=self._clear_all).pack(side=tk.LEFT, padx=2)
        ttk.Label(toolbar, text="", font=("", 1)).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 任务列表区域
        self._list_frame = ttk.Frame(self.win, padding=6)
        self._list_frame.pack(fill=tk.BOTH, expand=True)
        self._list_frame.bind("<Configure>", lambda e: self._on_resize(e))

        self._canvas = tk.Canvas(self._list_frame, bg="#FFFEF5", highlightthickness=0)
        self._scrollbar = ttk.Scrollbar(self._list_frame, orient=tk.VERTICAL,
                                         command=self._canvas.yview)
        self._scrollable = ttk.Frame(self._canvas)
        self._scrollable.bind("<Configure>",
                              lambda e: self._canvas.configure(
                                  scrollregion=self._canvas.bbox("all")))

        self._canvas_window = self._canvas.create_window((0, 0), window=self._scrollable,
                                                          anchor="nw")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_resize(self, event):
        canvas_width = event.width
        self._canvas.itemconfig(self._canvas_window, width=canvas_width)

    def _load_tasks(self):
        try:
            if TASKS_FILE.exists():
                data = json.loads(TASKS_FILE.read_text(encoding="utf-8-sig"))
                if isinstance(data, list):
                    self._tasks = data
        except Exception:
            self._tasks = []
        self._render()

    def _save_tasks(self):
        TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        TASKS_FILE.write_text(
            json.dumps(self._tasks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _render(self):
        for w in self._scrollable.winfo_children():
            w.destroy()
        self._check_vars.clear()

        pending = [t for t in self._tasks if not t.get("done", False)]
        done = [t for t in self._tasks if t.get("done", False)]

        if not self._tasks:
            empty_lbl = ttk.Label(self._scrollable,
                                  text=f"  {self._t('no_tasks')}  ",
                                  foreground="#999", font=("Microsoft YaHei", 12))
            empty_lbl.pack(pady=40)
            return

        # 待完成
        if pending:
            lbl = ttk.Label(self._scrollable, text=f"📌 {self._t('task_pending')}（{len(pending)}）",
                            font=("Microsoft YaHei", 11, "bold"), foreground="#FF8C00")
            lbl.pack(anchor=tk.W, pady=(6, 2))
            for t in pending:
                self._task_row(t)

        # 已完成
        if done:
            lbl = ttk.Label(self._scrollable, text=f"✅ {self._t('task_done')}（{len(done)}）",
                            font=("Microsoft YaHei", 11, "bold"), foreground="#228B22")
            lbl.pack(anchor=tk.W, pady=(12, 2))
            for t in done:
                self._task_row(t)

    def _task_row(self, task: dict):
        idx = task.get("id", str(id(task)))
        row = ttk.Frame(self._scrollable, padding=(4, 3))
        row.pack(fill=tk.X, pady=1)

        var = tk.BooleanVar(value=task.get("done", False))
        self._check_vars[idx] = var
        cb = ttk.Checkbutton(row, variable=var,
                             command=lambda t=task, v=var: self._toggle_done(t, v))
        cb.pack(side=tk.LEFT)

        info_frame = ttk.Frame(row)
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        name = task.get("task") or task.get("raw") or "未命名"
        name_lbl = ttk.Label(info_frame, text=name,
                             font=("Microsoft YaHei", 10, "overstrike" if task.get("done") else "normal"),
                             foreground="#888" if task.get("done") else "#333")
        name_lbl.pack(anchor=tk.W)

        detail_text = ""
        time_str = task.get("time") or ""
        if task.get("time_text"):
            time_str += f"（{task['time_text']}）"
        if time_str:
            detail_text += f"时间：{time_str}  "
        if task.get("place"):
            detail_text += f"地点：{task['place']}  "
        if task.get("notes"):
            detail_text += f"备注：{task['notes']}"

        if detail_text:
            detail_lbl = ttk.Label(info_frame, text=detail_text.strip(),
                                   font=("Microsoft YaHei", 8),
                                   foreground="#AAA" if task.get("done") else "#888")
            detail_lbl.pack(anchor=tk.W)

        # 删除按钮
        del_btn = ttk.Button(row, text="×", width=2,
                             command=lambda t=task: self._delete_task(t))
        del_btn.pack(side=tk.RIGHT, padx=(4, 0))

        if task.get("done"):
            row.configure(style="Done.TFrame")

    def _toggle_done(self, task: dict, var: tk.BooleanVar):
        task["done"] = var.get()
        self._save_tasks()
        self._render()

    def _delete_task(self, task: dict):
        tid = task.get("id", str(id(task)))
        self._tasks = [t for t in self._tasks if t.get("id", str(id(t))) != tid]
        self._save_tasks()
        self._render()

    def _clear_done(self):
        if messagebox.askyesno(self._t("task_list"), "确定清空所有已完成任务？"):
            self._tasks = [t for t in self._tasks if not t.get("done", False)]
            self._save_tasks()
            self._render()

    def _clear_all(self):
        if messagebox.askyesno(self._t("task_list"), "确定清空全部任务？"):
            self._tasks = []
            self._save_tasks()
            self._render()

    def add_tasks(self, new_tasks: list):
        for t in new_tasks:
            if isinstance(t, dict):
                task_item = {
                    "id": str(len(self._tasks) + 1),
                    "task": t.get("task") or t.get("raw", ""),
                    "time": t.get("time") or "",
                    "time_text": t.get("time_text") or "",
                    "time_start": t.get("time_start") or "",
                    "time_end": t.get("time_end") or "",
                    "place": t.get("place") or "",
                    "notes": t.get("notes") or "",
                    "raw": t.get("raw", ""),
                    "done": False,
                    "created_at": datetime.now().isoformat(),
                }
                self._tasks.append(task_item)
        self._save_tasks()
        self._render()

    def get_upcoming_tasks(self, minutes_ahead: int = 30):
        """获取即将到期的任务列表。"""
        now = datetime.now()
        upcoming = []
        for t in self._tasks:
            if t.get("done", False):
                continue
            time_str = t.get("time") or t.get("time_end") or t.get("time_start", "")
            if not time_str:
                continue
            try:
                if " " in time_str:
                    task_dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                else:
                    task_dt = datetime.strptime(time_str, "%Y-%m-%d")
                    task_dt = task_dt.replace(hour=23, minute=59)
                diff = (task_dt - now).total_seconds() / 60
                if 0 <= diff <= minutes_ahead:
                    upcoming.append((t, diff))
            except (ValueError, TypeError):
                continue
        return sorted(upcoming, key=lambda x: x[1])

    def refresh_config(self):
        self._cfg = load_config()
        self._lang = self._cfg.get("language", {}).get("ui_lang", "zh")
        self._strings = LANG_STRINGS.get(self._lang, LANG_STRINGS["zh"])
        self.win.title(self._t("task_list"))
        self._render()
