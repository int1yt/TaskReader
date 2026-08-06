"""TaskReader 桌宠 — 点击宠物弹出对话面板。"""
from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path
from datetime import datetime
import threading

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from task_reader.engine import TaskReader
from app.config import (
    load_config, save_config, PERSONALITIES, PET_STYLES,
    LANGUAGES, BEHAVIOR_PATTERNS, LANG_STRINGS,
)
from app.pet import PetWindow
from app.reminder import Reminder

TASKS_FILE = Path(os.environ.get("TASKREADER_CONFIG",
                 Path.home() / ".taskreader")) / "tasks.json"


class TaskReaderApp:
    def __init__(self):
        self._cfg = load_config()
        self._lang = self._cfg.get("language", {}).get("ui_lang", "zh")
        self._strings = LANG_STRINGS.get(self._lang, LANG_STRINGS["zh"])
        self._reader = TaskReader()
        self._tasks = []
        self._tray = None

        self.root = tk.Tk()
        self.root.withdraw()
        self._set_icon()

        self._pet = None
        self._chat_panel = None
        self._task_panel = None
        self._settings_win = None

        self._load_tasks()

        # 启动桌面宠物
        self._start_pet()
        self._start_reminder()

        if self._cfg.get("pet_behavior", {}).get("greeting_on_start", True):
            name = self._cfg.get("bot_profile", {}).get("name", "小读")
            self.root.after(1000, lambda: self._show_bubble(
                f"你好！我是{name}，点击我聊天，右键查看更多~", 5000))

    def _t(self, key):
        self._strings = LANG_STRINGS.get(self._lang, LANG_STRINGS["zh"])
        return self._strings.get(key, key)

    def _set_icon(self):
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

    # ── 桌面宠物 ──────────────────────────────────────────
    def _start_pet(self):
        self._pet = PetWindow(
            master=self.root,
            on_double_click=self._toggle_chat_panel,
            on_right_click=self._show_pet_menu,
        )

    def _show_bubble(self, text, duration=4000):
        if self._pet:
            try:
                self._pet.show_notification_bubble(text, duration)
            except Exception:
                pass

    def _show_pet_menu(self):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=self._t("chat"), command=self._toggle_chat_panel)
        menu.add_command(label=self._t("task_list"), command=self._toggle_task_panel)
        menu.add_separator()
        menu.add_command(label=self._t("settings"), command=self._open_settings)
        menu.add_separator()
        if self._pet:
            menu.add_command(label="隐藏宠物", command=lambda: self._pet.win.withdraw())
            menu.add_command(label="显示宠物", command=lambda: self._pet.win.deiconify())
        menu.add_command(label=self._t("exit"), command=self._exit_app)
        try:
            menu.tk_popup(self._pet.win.winfo_pointerx(),
                          self._pet.win.winfo_pointery())
        finally:
            menu.grab_release()

    # ── 聊天面板（点击宠物弹出） ──────────────────────────
    def _toggle_chat_panel(self):
        if self._chat_panel and self._chat_panel.winfo_exists():
            if self._chat_panel.state() == "normal":
                self._chat_panel.withdraw()
                return
            self._chat_panel.deiconify()
            self._chat_panel.lift()
            self._chat_panel.focus_force()
            return
        self._open_chat_panel()

    def _open_chat_panel(self):
        win = tk.Toplevel(self.root)
        win.title("聊天")
        win.overrideredirect(True)
        win.wm_attributes("-topmost", True)

        # 定位在宠物下方
        pet_x = self._pet.win.winfo_x()
        pet_y = self._pet.win.winfo_y()
        pet_size = self._pet._size
        win_w, win_h = 360, 420
        x = pet_x + pet_size // 2 - win_w // 2
        y = pet_y + pet_size + 6
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        x = max(0, min(x, screen_w - win_w))
        y = max(0, min(y, screen_h - win_h))
        win.geometry(f"{win_w}x{win_h}+{x}+{y}")

        # 外观
        bg = "#FFFEF5"
        header_bg = "#4A90D9"
        win.config(bg=bg)
        win.bind("<FocusOut>", lambda e: win.withdraw())

        # 顶部标题栏（可拖拽）
        title_f = tk.Frame(win, bg=header_bg, height=32)
        title_f.pack(fill=tk.X)
        title_f.pack_propagate(False)
        name = self._cfg.get("bot_profile", {}).get("name", "小读")
        tk.Label(title_f, text=f"  {name} 的聊天", bg=header_bg, fg="white",
                 font=("Microsoft YaHei", 10, "bold")).pack(side=tk.LEFT, pady=4)
        close_btn = tk.Label(title_f, text="✕  ", bg=header_bg, fg="white",
                             font=("Microsoft YaHei", 12), cursor="hand2")
        close_btn.pack(side=tk.RIGHT, pady=2)
        close_btn.bind("<Button-1>", lambda e: win.withdraw())

        # 拖拽标题栏
        def _drag_start(e):
            win._dx, win._dy = e.x, e.y
        def _drag_move(e):
            wx = win.winfo_x() + (e.x - win._dx)
            wy = win.winfo_y() + (e.y - win._dy)
            win.geometry(f"+{wx}+{wy}")
        title_f.bind("<ButtonPress-1>", _drag_start)
        title_f.bind("<B1-Motion>", _drag_move)

        # 聊天历史
        chat_area = tk.Text(win, wrap=tk.WORD, state=tk.DISABLED,
                            font=("Microsoft YaHei", 10), bg=bg, fg="#333",
                            relief=tk.FLAT, padx=8, pady=6, bd=0)
        chat_area.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 4))
        chat_area.tag_config("user", foreground="#0066CC",
                             font=("Microsoft YaHei", 10, "bold"))
        chat_area.tag_config("bot", foreground="#228B22",
                             font=("Microsoft YaHei", 10))
        chat_area.tag_config("task", foreground="#FF8C00",
                             font=("Microsoft YaHei", 10))

        def _append(text, tag):
            chat_area.config(state=tk.NORMAL)
            chat_area.insert(tk.END, text + "\n", tag)
            chat_area.see(tk.END)
            chat_area.config(state=tk.DISABLED)

        def _append_bot(text):
            _append(f"{name}：{text}", "bot")

        def _append_user(text):
            _append(f"你：{text}", "user")

        def _append_task(text):
            _append(text, "task")

        # 输入框
        input_f = tk.Frame(win, bg=bg)
        input_f.pack(fill=tk.X, padx=4, pady=(0, 6))
        input_entry = tk.Entry(input_f, font=("Microsoft YaHei", 10),
                               relief=tk.FLAT, bd=1)
        input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        input_entry.bind("<Return>", lambda e: _send())

        send_btn = tk.Label(input_f, text=" 发送 ", bg=header_bg, fg="white",
                            font=("Microsoft YaHei", 10), cursor="hand2",
                            padx=10, pady=2)
        send_btn.pack(side=tk.RIGHT, padx=(4, 0))
        send_btn.bind("<Button-1>", lambda e: _send())

        def _send():
            text = input_entry.get().strip()
            if not text:
                return
            input_entry.delete(0, tk.END)
            _append_user(text)

            use_llm = self._cfg.get("model", {}).get("use_llm", False)
            try:
                result = self._reader.parse_json(text, use_llm=use_llm)
            except Exception:
                _append_bot("抱歉，处理时出错了。")
                return

            if not result:
                _append_bot(self._cfg.get("reply_style", {}).get("no_task",
                            "没有识别到任务，换个说法试试？"))
                return

            style = self._cfg.get("reply_style", {})
            header = style.get("task_header", "收到！整理了 {count} 个任务：")
            _append_bot(header.format(count=len(result)))

            for i, t in enumerate(result, 1):
                name_t = t.get("task") or t.get("raw") or "任务"
                time_s = t.get("time") or ""
                tt = t.get("time_text") or ""
                time_d = f"{time_s}（{tt}）" if time_s and tt else (time_s or "未指定时间")
                extra = ""
                if t.get("place"):
                    extra += f" | {t['place']}"
                if t.get("notes"):
                    extra += f" | {t['notes']}"
                _append_task(f"  {i}. {name_t}")
                _append_task(f"     {time_d}{extra}")

            footer = style.get("task_footer", "")
            if footer:
                _append_bot(footer)

            self._add_tasks(result)
            if self._pet:
                self._pet.set_expression("happy")
                self.root.after(1800, lambda: self._pet.set_expression("normal"))
                self._show_bubble(f"已添加 {len(result)} 个任务~", 2500)

        _append_bot("告诉我你要做什么，我帮你分解成任务并按时提醒你~")
        input_entry.focus_set()

        self._chat_panel = win

    # ── 任务清单面板 ──────────────────────────────────────
    def _toggle_task_panel(self):
        if self._task_panel and self._task_panel.winfo_exists():
            if self._task_panel.state() == "normal":
                self._task_panel.withdraw()
                return
            self._task_panel.deiconify()
            self._task_panel.lift()
            self._task_panel.focus_force()
            return
        self._open_task_panel()

    def _open_task_panel(self):
        win = tk.Toplevel(self.root)
        win.title(self._t("task_list"))
        win.geometry("480x480")
        win.minsize(360, 300)
        try:
            win.iconbitmap(default="")
        except Exception:
            pass

        toolbar = ttk.Frame(win, padding=4)
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="清空已完成", command=self._clear_done).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="清空全部", command=self._clear_all).pack(side=tk.LEFT, padx=2)

        canvas = tk.Canvas(win, bg="#FFFEF5", highlightthickness=0)
        scrollbar = ttk.Scrollbar(win, orient=tk.VERTICAL, command=canvas.yview)
        list_frame = ttk.Frame(canvas)
        list_frame.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_canvas_resize(e):
            canvas.itemconfig(1, width=e.width)
        canvas.bind("<Configure>", _on_canvas_resize)

        def _render():
            for w in list_frame.winfo_children():
                w.destroy()
            if not self._tasks:
                ttk.Label(list_frame, text="  暂无任务  ", foreground="#999",
                          font=("Microsoft YaHei", 12)).pack(pady=40)
                return

            pending = [t for t in self._tasks if not t.get("done")]
            done = [t for t in self._tasks if t.get("done")]

            if pending:
                ttk.Label(list_frame, text=f"待完成（{len(pending)}）",
                          font=("Microsoft YaHei", 11, "bold"),
                          foreground="#FF8C00").pack(anchor=tk.W, pady=(6, 2))
                for t in pending:
                    _row(t)

            if done:
                ttk.Label(list_frame, text=f"已完成（{len(done)}）",
                          font=("Microsoft YaHei", 11, "bold"),
                          foreground="#228B22").pack(anchor=tk.W, pady=(12, 2))
                for t in done:
                    _row(t)

        def _row(task):
            r = ttk.Frame(list_frame, padding=(4, 3))
            r.pack(fill=tk.X, pady=1)

            var = tk.BooleanVar(value=task.get("done", False))
            ttk.Checkbutton(r, variable=var,
                            command=lambda t=task, v=var: _toggle(t, v)).pack(side=tk.LEFT)

            info = ttk.Frame(r)
            info.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

            name = task.get("task") or task.get("raw") or "未命名"
            fs = "overstrike" if task.get("done") else "normal"
            fg = "#888" if task.get("done") else "#333"
            ttk.Label(info, text=name, font=("Microsoft YaHei", 10, fs),
                      foreground=fg).pack(anchor=tk.W)

            detail = ""
            ts = task.get("time") or ""
            if task.get("time_text"):
                ts += f"（{task['time_text']}）"
            if ts:
                detail += f"时间：{ts}  "
            if task.get("place"):
                detail += f"地点：{task['place']}  "
            if task.get("notes"):
                detail += f"备注：{task['notes']}"
            if detail:
                ttk.Label(info, text=detail.strip(), font=("Microsoft YaHei", 8),
                          foreground="#AAA" if task.get("done") else "#888").pack(anchor=tk.W)

            ttk.Button(r, text="×", width=2,
                       command=lambda t=task: _delete(t)).pack(side=tk.RIGHT, padx=(4, 0))

        def _toggle(task, var):
            task["done"] = var.get()
            self._save_tasks()
            _render()

        def _delete(task):
            tid = task.get("id", str(id(task)))
            self._tasks = [t for t in self._tasks if t.get("id", str(id(t))) != tid]
            self._save_tasks()
            _render()

        _render()
        win.protocol("WM_DELETE_WINDOW", win.withdraw)
        self._task_panel = win

    # ── 设置窗口 ──────────────────────────────────────────
    def _open_settings(self):
        if self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.deiconify()
            self._settings_win.lift()
            self._settings_win.focus_force()
            return
        from .settings import SettingsWindow
        self._settings_win = SettingsWindow(master=self.root, on_save=self._on_settings_saved).win

    def _on_settings_saved(self, cfg):
        self._cfg = cfg
        self._lang = cfg.get("language", {}).get("ui_lang", "zh")
        self._strings = LANG_STRINGS.get(self._lang, LANG_STRINGS["zh"])
        if self._pet:
            self._pet.refresh_config()
        if hasattr(self, '_reminder') and self._reminder:
            self._reminder.refresh_config()

    # ── 任务管理 ──────────────────────────────────────────
    def _load_tasks(self):
        try:
            if TASKS_FILE.exists():
                self._tasks = json.loads(TASKS_FILE.read_text(encoding="utf-8-sig"))
                if not isinstance(self._tasks, list):
                    self._tasks = []
        except Exception:
            self._tasks = []

    def _save_tasks(self):
        TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        TASKS_FILE.write_text(json.dumps(self._tasks, ensure_ascii=False, indent=2), encoding="utf-8")

    def _add_tasks(self, new_tasks):
        for t in new_tasks:
            if isinstance(t, dict):
                self._tasks.append({
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
                })
        self._save_tasks()

    def _clear_done(self):
        self._tasks = [t for t in self._tasks if not t.get("done")]
        self._save_tasks()

    def _clear_all(self):
        self._tasks = []
        self._save_tasks()

    def get_upcoming_tasks(self, minutes_ahead=30):
        now = datetime.now()
        upcoming = []
        for t in self._tasks:
            if t.get("done"):
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

    # ── 提醒系统 ──────────────────────────────────────────
    def _start_reminder(self):
        self._reminder = Reminder(task_panel=self, pet_window=self._pet)
        self._reminder.start()

    # ── 系统托盘 ──────────────────────────────────────────
    def start_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw

            def _make_icon(size=64):
                img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                draw.ellipse([4, 4, size - 4, size - 4], fill=(66, 133, 244, 255))
                draw.text((size // 2, size // 2), "T", fill="white", anchor="mm")
                return img

            menu = pystray.Menu(
                pystray.MenuItem("聊天", lambda: self.root.after(0, self._toggle_chat_panel)),
                pystray.MenuItem("任务清单", lambda: self.root.after(0, self._toggle_task_panel)),
                pystray.MenuItem("设置", lambda: self.root.after(0, self._open_settings)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", lambda: self.root.after(0, self._exit_app)),
            )
            self._tray = pystray.Icon("TaskReader", _make_icon(), "TaskReader 桌宠", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
        except ImportError:
            pass

    def _exit_app(self):
        try:
            if self._pet:
                self._pet.stop_anim()
                self._pet.win.destroy()
            if hasattr(self, '_reminder') and self._reminder:
                self._reminder.stop()
            if self._tray:
                self._tray.stop()
        except Exception:
            pass
        self.root.destroy()
        os._exit(0)

    def run(self):
        self.start_tray()
        self.root.mainloop()


def main():
    app = TaskReaderApp()
    app.run()


if __name__ == "__main__":
    main()
