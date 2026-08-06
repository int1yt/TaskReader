"""设置窗口：机器人个性化配置界面。"""
from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox

from .config import (
    load_config, save_config, PERSONALITIES,
    PET_STYLES, LANGUAGES, BEHAVIOR_PATTERNS, LANG_STRINGS,
)


class SettingsWindow:
    def __init__(self, master=None, on_save=None):
        self._on_save = on_save
        self._cfg = load_config()
        self._lang = self._cfg.get("language", {}).get("ui_lang", "zh")
        self._strings = LANG_STRINGS.get(self._lang, LANG_STRINGS["zh"])

        self.win = tk.Toplevel(master) if master else tk.Tk()
        self.win.title(self._t("settings"))
        self.win.geometry("560x640")
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        try:
            self.win.iconbitmap(default="")
        except Exception:
            pass

        self._build()
        self.win.focus_force()

    def _t(self, key):
        self._strings = LANG_STRINGS.get(self._lang, LANG_STRINGS["zh"])
        return self._strings.get(key, key)

    def _build(self):
        notebook = ttk.Notebook(self.win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._tab_profile(notebook)
        self._tab_appearance(notebook)
        self._tab_behavior(notebook)
        self._tab_reply(notebook)
        self._tab_reminder(notebook)
        self._tab_language(notebook)
        self._tab_model(notebook)
        self._tab_bot(notebook)

        btn_frame = ttk.Frame(self.win)
        btn_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        ttk.Button(btn_frame, text=self._t("save"), command=self._save).pack(
            side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text=self._t("cancel"), command=self._on_close).pack(
            side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text=self._t("reset"), command=self._reset).pack(
            side=tk.LEFT, padx=4)

    # ---- 机器人资料页 ----
    def _tab_profile(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="机器人资料")

        p = self._cfg["bot_profile"]
        row = 0

        ttk.Label(f, text="机器人名称：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_name = tk.StringVar(value=p.get("name", ""))
        ttk.Entry(f, textvariable=self._var_name, width=30).grid(
            row=row, column=1, sticky=tk.W, pady=4, padx=8)
        row += 1

        ttk.Label(f, text="昵称 / 备注：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_nick = tk.StringVar(value=p.get("nickname", ""))
        ttk.Entry(f, textvariable=self._var_nick, width=30).grid(
            row=row, column=1, sticky=tk.W, pady=4, padx=8)
        row += 1

        ttk.Label(f, text="性格 / 人设：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_person = tk.StringVar(value=p.get("personality", "friendly"))
        cb = ttk.Combobox(f, textvariable=self._var_person, width=18, state="readonly")
        cb["values"] = [f"{k}（{v}）" for k, v in PERSONALITIES.items()]
        cb.current(list(PERSONALITIES.keys()).index(self._var_person.get())
                   if self._var_person.get() in PERSONALITIES else 0)
        cb.grid(row=row, column=1, sticky=tk.W, pady=4, padx=8)
        row += 1

        ttk.Label(f, text="语气风格：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_tone = tk.StringVar(value=p.get("tone", "casual"))
        tone_cb = ttk.Combobox(f, textvariable=self._var_tone, width=18, state="readonly")
        tone_cb["values"] = ["casual - 随意", "formal - 正式", "warm - 温暖", "humorous - 幽默"]
        tone_cb.current(0)
        tone_cb.grid(row=row, column=1, sticky=tk.W, pady=4, padx=8)
        row += 1

        ttk.Label(f, text="显示签名：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_sig = tk.BooleanVar(value=p.get("signature", True))
        ttk.Checkbutton(f, variable=self._var_sig, text="回复末尾附带机器人名称").grid(
            row=row, column=1, sticky=tk.W, pady=4, padx=8)

    # ---- 外观页 ----
    def _tab_appearance(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="宠物外观")

        a = self._cfg.get("pet_appearance", {})
        row = 0

        ttk.Label(f, text="宠物品类：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_style = tk.StringVar(value=a.get("style", "cat"))
        cb = ttk.Combobox(f, textvariable=self._var_style, width=18, state="readonly")
        cb["values"] = [f"{k}（{v}）" for k, v in PET_STYLES.items()]
        keys = list(PET_STYLES.keys())
        cb.current(keys.index(self._var_style.get()) if self._var_style.get() in keys else 0)
        cb.grid(row=row, column=1, sticky=tk.W, pady=4, padx=8)
        row += 1

        ttk.Label(f, text="主体颜色：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_color = tk.StringVar(value=a.get("color", "#FF8C00"))
        color_frame = ttk.Frame(f)
        color_frame.grid(row=row, column=1, sticky=tk.W, pady=4, padx=8)
        ttk.Entry(color_frame, textvariable=self._var_color, width=14).pack(side=tk.LEFT, padx=(0, 4))
        self._color_btn1 = tk.Button(color_frame, text="  ", bg=self._var_color.get(),
                                      width=2, relief=tk.FLAT, command=self._pick_main_color)
        self._color_btn1.pack(side=tk.LEFT)
        ttk.Label(f, text="（16进制色号）", foreground="#888").grid(row=row, column=2, sticky=tk.W, padx=4)
        row += 1

        ttk.Label(f, text="装饰颜色：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_accent = tk.StringVar(value=a.get("accent_color", "#FF6347"))
        accent_frame = ttk.Frame(f)
        accent_frame.grid(row=row, column=1, sticky=tk.W, pady=4, padx=8)
        ttk.Entry(accent_frame, textvariable=self._var_accent, width=14).pack(side=tk.LEFT, padx=(0, 4))
        self._color_btn2 = tk.Button(accent_frame, text="  ", bg=self._var_accent.get(),
                                      width=2, relief=tk.FLAT, command=self._pick_accent_color)
        self._color_btn2.pack(side=tk.LEFT)
        row += 1

        ttk.Label(f, text="眼睛颜色：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_eye = tk.StringVar(value=a.get("eye_color", "#2C3E50"))
        eye_frame = ttk.Frame(f)
        eye_frame.grid(row=row, column=1, sticky=tk.W, pady=4, padx=8)
        ttk.Entry(eye_frame, textvariable=self._var_eye, width=14).pack(side=tk.LEFT, padx=(0, 4))
        self._color_btn3 = tk.Button(eye_frame, text="  ", bg=self._var_eye.get(),
                                      width=2, relief=tk.FLAT, command=self._pick_eye_color)
        self._color_btn3.pack(side=tk.LEFT)
        row += 1

        ttk.Label(f, text="宠物大小：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_size = tk.IntVar(value=a.get("size", 120))
        size_scale = ttk.Scale(f, from_=80, to=200, variable=self._var_size,
                                orient=tk.HORIZONTAL, length=200)
        size_scale.grid(row=row, column=1, sticky=tk.W, pady=4, padx=8)
        size_lbl = ttk.Label(f, text=str(self._var_size.get()), width=4)
        size_lbl.grid(row=row, column=2, sticky=tk.W)
        self._var_size.trace_add("write", lambda *a: size_lbl.config(text=str(self._var_size.get())))
        row += 1

        self._var_topmost = tk.BooleanVar(value=a.get("always_on_top", True))
        ttk.Checkbutton(f, variable=self._var_topmost,
                        text="始终显示在最前").grid(
            row=row, column=1, sticky=tk.W, pady=4, padx=8)
        row += 1

        ttk.Label(f, text="透明度：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_opacity = tk.DoubleVar(value=a.get("opacity", 0.95))
        op_scale = ttk.Scale(f, from_=0.3, to=1.0, variable=self._var_opacity,
                              orient=tk.HORIZONTAL, length=200)
        op_scale.grid(row=row, column=1, sticky=tk.W, pady=4, padx=8)
        op_lbl = ttk.Label(f, text=f"{self._var_opacity.get():.0%}", width=5)
        op_lbl.grid(row=row, column=2, sticky=tk.W)
        self._var_opacity.trace_add("write", lambda *a: op_lbl.config(
            text=f"{min(self._var_opacity.get(), 1.0):.0%}"))

    def _pick_main_color(self):
        from tkinter import colorchooser
        c = colorchooser.askcolor(color=self._var_color.get(), title="选择主体颜色")
        if c[1]:
            self._var_color.set(c[1])
            self._color_btn1.config(bg=c[1])

    def _pick_accent_color(self):
        from tkinter import colorchooser
        c = colorchooser.askcolor(color=self._var_accent.get(), title="选择装饰颜色")
        if c[1]:
            self._var_accent.set(c[1])
            self._color_btn2.config(bg=c[1])

    def _pick_eye_color(self):
        from tkinter import colorchooser
        c = colorchooser.askcolor(color=self._var_eye.get(), title="选择眼睛颜色")
        if c[1]:
            self._var_eye.set(c[1])
            self._color_btn3.config(bg=c[1])

    # ---- 行为页 ----
    def _tab_behavior(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="宠物行为")

        b = self._cfg.get("pet_behavior", {})
        row = 0

        self._var_idle_anim = tk.BooleanVar(value=b.get("idle_animations", True))
        ttk.Checkbutton(f, variable=self._var_idle_anim,
                        text="启用待机动画（呼吸/微动）").grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=4)
        row += 1

        self._var_greeting = tk.BooleanVar(value=b.get("greeting_on_start", True))
        ttk.Checkbutton(f, variable=self._var_greeting,
                        text="启动时打招呼").grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=4)
        row += 1

        self._var_react = tk.BooleanVar(value=b.get("react_to_messages", True))
        ttk.Checkbutton(f, variable=self._var_react,
                        text="收到消息时做出反应").grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=4)
        row += 1

        ttk.Label(f, text="活动节奏：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_speed = tk.StringVar(value=b.get("idle_speed", "normal"))
        speed_cb = ttk.Combobox(f, textvariable=self._var_speed, width=18, state="readonly")
        speed_cb["values"] = [f"{k}（{v}）" for k, v in BEHAVIOR_PATTERNS.items()]
        keys = list(BEHAVIOR_PATTERNS.keys())
        speed_cb.current(keys.index(self._var_speed.get()) if self._var_speed.get() in keys else 0)
        speed_cb.grid(row=row, column=1, sticky=tk.W, pady=4, padx=8)

    # ---- 回复风格页 ----
    def _tab_reply(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="回复风格")

        s = self._cfg["reply_style"]
        row = 0

        ttk.Label(f, text="任务头部模板：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_header = tk.StringVar(value=s.get("task_header", ""))
        ttk.Entry(f, textvariable=self._var_header, width=45).grid(
            row=row, column=1, columnspan=2, sticky=tk.EW, pady=4, padx=8)
        row += 1

        ttk.Label(f, text="每条任务模板：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_item = tk.StringVar(value=s.get("task_item", ""))
        ttk.Entry(f, textvariable=self._var_item, width=45).grid(
            row=row, column=1, columnspan=2, sticky=tk.EW, pady=4, padx=8)
        row += 1

        ttk.Label(f, text="任务尾部模板：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_footer = tk.StringVar(value=s.get("task_footer", ""))
        ttk.Entry(f, textvariable=self._var_footer, width=45).grid(
            row=row, column=1, columnspan=2, sticky=tk.EW, pady=4, padx=8)
        row += 1

        ttk.Label(f, text="无任务回复：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_no_task = tk.StringVar(value=s.get("no_task", ""))
        ttk.Entry(f, textvariable=self._var_no_task, width=45).grid(
            row=row, column=1, columnspan=2, sticky=tk.EW, pady=4, padx=8)
        row += 1

        self._var_emoji = tk.BooleanVar(value=s.get("use_emoji", False))
        ttk.Checkbutton(f, variable=self._var_emoji,
                        text="使用表情符号（emoji）").grid(
            row=row, column=1, sticky=tk.W, pady=8, padx=8)

        ttk.Label(f, text="可用变量：{count} {index} {name} {time} {note}",
                  foreground="#888").grid(row=row + 1, column=1, sticky=tk.W, padx=8)

    # ---- 提醒页 ----
    def _tab_reminder(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="提醒设置")

        r = self._cfg.get("reminder", {})
        row = 0

        self._var_remind_enabled = tk.BooleanVar(value=r.get("enabled", True))
        ttk.Checkbutton(f, variable=self._var_remind_enabled,
                        text="启用任务提醒").grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=4)
        row += 1

        ttk.Label(f, text="提前  （分钟）：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_advance_30 = tk.IntVar(value=r.get("advance_minutes", 30))
        ttk.Spinbox(f, from_=0, to=120, textvariable=self._var_advance_30,
                    width=8).grid(row=row, column=1, sticky=tk.W, pady=4, padx=8)
        row += 1

        ttk.Label(f, text="提前  （小时）：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_advance_1 = tk.IntVar(value=r.get("advance_hours_1", 1))
        ttk.Spinbox(f, from_=0, to=24, textvariable=self._var_advance_1,
                    width=8).grid(row=row, column=1, sticky=tk.W, pady=4, padx=8)
        row += 1

        ttk.Label(f, text="提前 （小时）：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_advance_24 = tk.IntVar(value=r.get("advance_hours_2", 24))
        ttk.Spinbox(f, from_=0, to=72, textvariable=self._var_advance_24,
                    width=8).grid(row=row, column=1, sticky=tk.W, pady=4, padx=8)
        row += 1

        ttk.Label(f, text="气泡显示 （秒）：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_popup_dur = tk.IntVar(value=r.get("popup_duration", 10))
        ttk.Spinbox(f, from_=3, to=60, textvariable=self._var_popup_dur,
                    width=8).grid(row=row, column=1, sticky=tk.W, pady=4, padx=8)
        row += 1

        self._var_sound = tk.BooleanVar(value=r.get("sound_enabled", True))
        ttk.Checkbutton(f, variable=self._var_sound,
                        text="播放提示音").grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=4)

    # ---- 语言页 ----
    def _tab_language(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="语言设置")

        l = self._cfg.get("language", {})
        row = 0

        ttk.Label(f, text="界面语言：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_ui_lang = tk.StringVar(value=l.get("ui_lang", "zh"))
        lang_cb = ttk.Combobox(f, textvariable=self._var_ui_lang, width=20, state="readonly")
        lang_cb["values"] = [f"{k} - {v}" for k, v in LANGUAGES.items()]
        keys = list(LANGUAGES.keys())
        lang_cb.current(keys.index(l.get("ui_lang", "zh")) if l.get("ui_lang", "zh") in keys else 0)
        lang_cb.grid(row=row, column=1, sticky=tk.W, pady=4, padx=8)
        ttk.Label(f, text="（需重启生效）", foreground="#888").grid(
            row=row, column=2, sticky=tk.W, padx=4)
        row += 1

        self._var_traditional = tk.BooleanVar(value=l.get("use_traditional", False))
        ttk.Checkbutton(f, variable=self._var_traditional,
                        text="使用繁体中文（覆写简体中文）").grid(
            row=row, column=1, sticky=tk.W, pady=4, padx=8)

    # ---- 模型设置页 ----
    def _tab_model(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="模型设置")

        m = self._cfg["model"]
        row = 0

        ttk.Label(f, text="Ollama 地址：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_host = tk.StringVar(value=m.get("host", ""))
        ttk.Entry(f, textvariable=self._var_host, width=35).grid(
            row=row, column=1, sticky=tk.W, pady=4, padx=8)
        row += 1

        ttk.Label(f, text="模型名称：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self._var_model = tk.StringVar(value=m.get("model", ""))
        ttk.Entry(f, textvariable=self._var_model, width=35).grid(
            row=row, column=1, sticky=tk.W, pady=4, padx=8)
        ttk.Label(f, text="（如 qwen3:0.6b）",
                  foreground="#888").grid(row=row, column=2, sticky=tk.W, padx=4)
        row += 1

        self._var_llm = tk.BooleanVar(value=m.get("use_llm", False))
        ttk.Checkbutton(f, variable=self._var_llm,
                        text="启用 LLM 增强识别（需要 Ollama 运行中）").grid(
            row=row, column=1, sticky=tk.W, pady=8, padx=8)

    # ---- 运行设置页 ----
    def _tab_bot(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="运行设置")

        b = self._cfg["bot"]
        row = 0

        self._var_autostart = tk.BooleanVar(value=b.get("auto_start", False))
        ttk.Checkbutton(f, variable=self._var_autostart,
                        text="开机自动启动").grid(
            row=row, column=0, sticky=tk.W, pady=4)
        row += 1

        self._var_listen_all = tk.BooleanVar(value=b.get("listen_all", True))
        ttk.Checkbutton(f, variable=self._var_listen_all,
                        text="监听所有会话").grid(
            row=row, column=0, sticky=tk.W, pady=4)
        row += 1

        ttk.Label(f, text="指定监听联系人（每行一个）：").grid(
            row=row, column=0, sticky=tk.W, pady=(8, 2))
        row += 1

        self._var_listen_list = tk.Text(f, width=40, height=5)
        self._var_listen_list.insert("1.0", "\n".join(b.get("listen_list", [])))
        self._var_listen_list.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        row += 1

        self._var_reply_self = tk.BooleanVar(value=b.get("reply_to_self", False))
        ttk.Checkbutton(f, variable=self._var_reply_self,
                        text="回复自己发送的消息（调试用）").grid(
            row=row, column=0, sticky=tk.W, pady=(8, 2))

    # ---- 操作 ----
    def _save(self):
        try:
            self._cfg["bot_profile"] = {
                "name": self._var_name.get().strip(),
                "nickname": self._var_nick.get().strip(),
                "personality": self._var_person.get().split("（")[0]
                if "（" in self._var_person.get() else self._var_person.get(),
                "tone": self._var_tone.get().split(" - ")[0],
                "signature": self._var_sig.get(),
            }
            self._cfg["reply_style"] = {
                "task_header": self._var_header.get(),
                "task_item": self._var_item.get(),
                "task_footer": self._var_footer.get(),
                "no_task": self._var_no_task.get(),
                "use_emoji": self._var_emoji.get(),
            }
            self._cfg["model"] = {
                "host": self._var_host.get().strip(),
                "model": self._var_model.get().strip(),
                "use_llm": self._var_llm.get(),
            }
            self._cfg["bot"] = {
                "auto_start": self._var_autostart.get(),
                "listen_all": self._var_listen_all.get(),
                "listen_list": [
                    line.strip() for line in
                    self._var_listen_list.get("1.0", tk.END).split("\n")
                    if line.strip()
                ],
                "reply_to_self": self._var_reply_self.get(),
            }
            self._cfg["pet_appearance"] = {
                "style": self._var_style.get().split("（")[0]
                if "（" in self._var_style.get() else self._var_style.get(),
                "color": self._var_color.get().strip(),
                "accent_color": self._var_accent.get().strip(),
                "eye_color": self._var_eye.get().strip(),
                "size": self._var_size.get(),
                "always_on_top": self._var_topmost.get(),
                "opacity": round(self._var_opacity.get(), 2),
            }
            self._cfg["pet_behavior"] = {
                "idle_animations": self._var_idle_anim.get(),
                "greeting_on_start": self._var_greeting.get(),
                "react_to_messages": self._var_react.get(),
                "idle_speed": self._var_speed.get().split("（")[0]
                if "（" in self._var_speed.get() else self._var_speed.get(),
                "auto_hide_taskbar": True,
            }
            self._cfg["reminder"] = {
                "enabled": self._var_remind_enabled.get(),
                "advance_minutes": self._var_advance_30.get(),
                "advance_hours_1": self._var_advance_1.get(),
                "advance_hours_2": self._var_advance_24.get(),
                "sound_enabled": self._var_sound.get(),
                "popup_duration": self._var_popup_dur.get(),
            }
            ui_lang = self._var_ui_lang.get().split(" - ")[0] if " - " in self._var_ui_lang.get() else self._var_ui_lang.get()
            self._cfg["language"] = {
                "ui_lang": ui_lang,
                "use_traditional": self._var_traditional.get(),
            }
            save_config(self._cfg)
            self._set_autostart(self._var_autostart.get())
            messagebox.showinfo("设置", "设置已保存，部分选项需重启应用后生效。")
            if self._on_save:
                self._on_save(self._cfg)
        except Exception as e:
            messagebox.showerror("错误", f"保存失败：{e}")

    def _reset(self):
        if messagebox.askyesno("确认", "恢复默认设置将覆盖当前配置，确定吗？"):
            from .config import DEFAULT_CONFIG, save_config as sv
            self._cfg = __import__("copy").deepcopy(DEFAULT_CONFIG)
            sv(self._cfg)
            self.win.destroy()
            SettingsWindow(master=self.win.master, on_save=self._on_save)

    def _on_close(self):
        self.win.destroy()

    @staticmethod
    def _set_autostart(enabled: bool):
        import sys
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "TaskReaderPet"
        try:
            if enabled:
                pythonw = sys.executable.replace("python.exe", "pythonw.exe")
                project_dir = os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__)))
                launch_cmd = (
                    f'cmd /c cd /d "{project_dir}" && '
                    f'start "" "{pythonw}" -m app.main'
                )
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path,
                                     0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, launch_cmd)
                winreg.CloseKey(key)
            else:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path,
                                     0, winreg.KEY_SET_VALUE)
                try:
                    winreg.DeleteValue(key, app_name)
                except OSError:
                    pass
                winreg.CloseKey(key)
        except Exception:
            pass
