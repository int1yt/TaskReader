"""桌面宠物窗口：可拖拽的悬浮角色，支持多种外观和动画。"""
from __future__ import annotations

import math
import random
import tkinter as tk
from tkinter import ttk
import threading
import time

from .config import load_config, PET_STYLES


class PetWindow:
    def __init__(self, master=None, on_double_click=None, on_right_click=None):
        self._cfg = load_config()
        self._master = master
        self._on_double_click = on_double_click
        self._on_right_click = on_right_click

        self.win = tk.Toplevel(master) if master else tk.Tk()
        self._pet_cfg = self._cfg.get("pet_appearance", {})
        self._behavior_cfg = self._cfg.get("pet_behavior", {})

        size = self._pet_cfg.get("size", 120)
        screen_w = self.win.winfo_screenwidth()
        screen_h = self.win.winfo_screenheight()
        px = screen_w - size - 60
        py = screen_h // 4
        self.win.geometry(f"{size}x{size}+{px}+{py}")
        self.win.overrideredirect(True)
        self.win.wm_attributes("-topmost", self._pet_cfg.get("always_on_top", True))
        self.win.wm_attributes("-transparentcolor", "black")
        self.win.wm_attributes("-alpha", self._pet_cfg.get("opacity", 0.95))
        self.win.config(bg="black")

        self.canvas = tk.Canvas(
            self.win, width=size, height=size,
            bg="black", highlightthickness=0, bd=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 拖拽
        self._drag_x = 0
        self._drag_y = 0
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_move)
        self.canvas.bind("<Double-Button-1>", lambda e: self._handle_double_click())
        self.canvas.bind("<ButtonPress-3>", lambda e: self._handle_right_click())
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)

        self._anim_frame = 0
        self._anim_active = False
        self._eye_blink_timer = 0
        self._idle_timer = 0
        self._expression = "normal"
        self._size = size

        self.draw()
        self._start_anim()

    @property
    def style(self):
        return self._pet_cfg.get("style", "cat")

    @property
    def color(self):
        return self._pet_cfg.get("color", "#FF8C00")

    @property
    def accent_color(self):
        return self._pet_cfg.get("accent_color", "#FF6347")

    def refresh_config(self):
        self._cfg = load_config()
        self._pet_cfg = self._cfg.get("pet_appearance", {})
        self._behavior_cfg = self._cfg.get("pet_behavior", {})
        self.win.wm_attributes("-topmost", self._pet_cfg.get("always_on_top", True))
        self.win.wm_attributes("-alpha", self._pet_cfg.get("opacity", 0.95))
        new_size = self._pet_cfg.get("size", 120)
        if new_size != self._size:
            self._size = new_size
            self.win.geometry(f"{new_size}x{new_size}+{self.win.winfo_x()}+{self.win.winfo_y()}")
            self.canvas.config(width=new_size, height=new_size)
        self.draw()

    def set_expression(self, expression: str):
        self._expression = expression
        self.draw()

    # ---- 绘制 ----
    def draw(self):
        self.canvas.delete("all")
        style = self.style
        if style == "cat":
            self._draw_cat()
        elif style == "dog":
            self._draw_dog()
        elif style == "rabbit":
            self._draw_rabbit()
        elif style == "robot":
            self._draw_robot()
        elif style == "ghost":
            self._draw_ghost()
        elif style == "penguin":
            self._draw_penguin()
        else:
            self._draw_cat()

    def _draw_cat(self):
        W, H = self._size, self._size
        c = self.canvas
        color = self.color
        accent = self.accent_color
        eye_color = self._pet_cfg.get("eye_color", "#2C3E50")

        # 耳朵
        ear_h = H * 0.25
        c.create_polygon(W * 0.15, H * 0.28, W * 0.08, H * 0.05, W * 0.28, H * 0.20,
                         fill=color, outline="")
        c.create_polygon(W * 0.85, H * 0.28, W * 0.92, H * 0.05, W * 0.72, H * 0.20,
                         fill=color, outline="")
        # 内耳
        c.create_polygon(W * 0.18, H * 0.26, W * 0.13, H * 0.10, W * 0.26, H * 0.22,
                         fill="#FFB6C1", outline="")
        c.create_polygon(W * 0.82, H * 0.26, W * 0.87, H * 0.10, W * 0.74, H * 0.22,
                         fill="#FFB6C1", outline="")

        # 头
        c.create_oval(W * 0.10, H * 0.20, W * 0.90, H * 0.80, fill=color, outline="")

        # 眼睛
        blink = self._anim_frame % 120 > 115
        eye_y = H * 0.42
        eye_radius = W * 0.06
        if blink:
            c.create_line(W * 0.30, eye_y, W * 0.42, eye_y, fill=eye_color, width=3)
            c.create_line(W * 0.58, eye_y, W * 0.70, eye_y, fill=eye_color, width=3)
        else:
            c.create_oval(W * 0.30 - eye_radius, eye_y - eye_radius * 1.2,
                          W * 0.30 + eye_radius, eye_y + eye_radius * 0.8,
                          fill=eye_color, outline="")
            c.create_oval(W * 0.70 - eye_radius, eye_y - eye_radius * 1.2,
                          W * 0.70 + eye_radius, eye_y + eye_radius * 0.8,
                          fill=eye_color, outline="")
            # 高光
            c.create_oval(W * 0.30 - 2, eye_y - 5, W * 0.30 + 3, eye_y,
                          fill="white", outline="")
            c.create_oval(W * 0.70 - 2, eye_y - 5, W * 0.70 + 3, eye_y,
                          fill="white", outline="")

        # 鼻子
        c.create_polygon(W * 0.47, H * 0.52, W * 0.53, H * 0.52,
                         W * 0.50, H * 0.55, fill=accent, outline="")

        # 嘴巴
        expr = self._expression
        if expr == "happy":
            c.create_arc(W * 0.38, H * 0.48, W * 0.62, H * 0.62, start=0, extent=-180,
                         style="arc", outline=eye_color, width=2)
        elif expr == "surprised":
            c.create_oval(W * 0.42, H * 0.54, W * 0.58, H * 0.60,
                          fill=eye_color, outline="")
        elif expr == "thinking":
            c.create_oval(W * 0.44, H * 0.56, W * 0.56, H * 0.62,
                          fill="#FFB6C1", outline=eye_color, width=1)
        else:
            c.create_arc(W * 0.40, H * 0.60, W * 0.60, H * 0.52, start=0, extent=180,
                         style="arc", outline=eye_color, width=2)

        # 胡须
        w_maxs = [(W * 0.15, W * 0.35, H * 0.52), (W * 0.65, W * 0.85, H * 0.52)]
        for x1, x2, y in w_maxs:
            c.create_line(x1, y, x2, y - 5, fill="#888", width=1)
            c.create_line(x1, y, x2, y, fill="#888", width=1)
            c.create_line(x1, y, x2, y + 5, fill="#888", width=1)

    def _draw_dog(self):
        W, H = self._size, self._size
        c = self.canvas
        color = self.color
        accent = self.accent_color
        eye_color = self._pet_cfg.get("eye_color", "#2C3E50")

        # 垂耳
        c.create_oval(W * 0.02, H * 0.10, W * 0.25, H * 0.45, fill="#8B4513", outline="")
        c.create_oval(W * 0.75, H * 0.10, W * 0.98, H * 0.45, fill="#8B4513", outline="")

        # 头
        c.create_oval(W * 0.10, H * 0.18, W * 0.90, H * 0.80, fill=color, outline="")

        # 眼
        blink = self._anim_frame % 120 > 115
        eye_y = H * 0.40
        if not blink:
            c.create_oval(W * 0.28, eye_y - 6, W * 0.40, eye_y + 6, fill=eye_color, outline="")
            c.create_oval(W * 0.60, eye_y - 6, W * 0.72, eye_y + 6, fill=eye_color, outline="")
            c.create_oval(W * 0.30, eye_y - 3, W * 0.33, eye_y, fill="white", outline="")
            c.create_oval(W * 0.62, eye_y - 3, W * 0.65, eye_y, fill="white", outline="")
        else:
            c.create_line(W * 0.26, eye_y, W * 0.42, eye_y, fill=eye_color, width=3)
            c.create_line(W * 0.58, eye_y, W * 0.74, eye_y, fill=eye_color, width=3)

        # 鼻子
        c.create_oval(W * 0.44, H * 0.48, W * 0.56, H * 0.55, fill="#1a1a1a", outline="")

        # 嘴
        expr = self._expression
        if expr == "happy":
            c.create_arc(W * 0.35, H * 0.50, W * 0.65, H * 0.68, start=0, extent=-180,
                         style="arc", outline=eye_color, width=2)
            c.create_polygon(W * 0.42, H * 0.55, W * 0.50, H * 0.62, W * 0.58, H * 0.55,
                             fill="#FF6B6B", outline="")
        else:
            c.create_arc(W * 0.38, H * 0.62, W * 0.62, H * 0.54, start=0, extent=180,
                         style="arc", outline=eye_color, width=2)

    def _draw_rabbit(self):
        W, H = self._size, self._size
        c = self.canvas
        color = self.color
        accent = self.accent_color
        eye_color = self._pet_cfg.get("eye_color", "#2C3E50")

        # 长耳
        c.create_oval(W * 0.22, H * 0.02, W * 0.38, H * 0.28, fill=color, outline="")
        c.create_oval(W * 0.24, H * 0.06, W * 0.36, H * 0.24, fill="#FFB6C1", outline="")
        c.create_oval(W * 0.62, H * 0.02, W * 0.78, H * 0.28, fill=color, outline="")
        c.create_oval(W * 0.64, H * 0.06, W * 0.76, H * 0.24, fill="#FFB6C1", outline="")

        # 头
        c.create_oval(W * 0.12, H * 0.22, W * 0.88, H * 0.82, fill=color, outline="")

        # 眼
        blink = self._anim_frame % 120 > 115
        eye_y = H * 0.44
        if not blink:
            c.create_oval(W * 0.28, eye_y - 6, W * 0.40, eye_y + 6, fill=eye_color, outline="")
            c.create_oval(W * 0.60, eye_y - 6, W * 0.72, eye_y + 6, fill=eye_color, outline="")
            c.create_oval(W * 0.30, eye_y - 3, W * 0.33, eye_y, fill="white", outline="")
            c.create_oval(W * 0.62, eye_y - 3, W * 0.65, eye_y, fill="white", outline="")
        else:
            c.create_line(W * 0.26, eye_y, W * 0.42, eye_y, fill=eye_color, width=3)
            c.create_line(W * 0.58, eye_y, W * 0.74, eye_y, fill=eye_color, width=3)

        # 鼻子
        c.create_polygon(W * 0.47, H * 0.54, W * 0.53, H * 0.54,
                         W * 0.50, H * 0.57, fill=accent, outline="")
        # 嘴 - X形
        c.create_line(W * 0.46, H * 0.58, W * 0.54, H * 0.64, fill=eye_color, width=2)
        c.create_line(W * 0.54, H * 0.58, W * 0.46, H * 0.64, fill=eye_color, width=2)

    def _draw_robot(self):
        W, H = self._size, self._size
        c = self.canvas
        color = self.color
        accent = self.accent_color
        eye_color = self._pet_cfg.get("eye_color", "#00FF88")

        # 天线
        c.create_line(W * 0.50, H * 0.02, W * 0.50, H * 0.10, fill=color, width=3)
        c.create_oval(W * 0.45, H * 0.0, W * 0.55, H * 0.06, fill=accent, outline="")

        # 头 - 方形
        c.create_rectangle(W * 0.15, H * 0.12, W * 0.85, H * 0.78, fill=color, outline="")

        # 眼睛 - LED风格
        eye_y = H * 0.35
        c.create_rect = c.create_rectangle
        c.create_oval(W * 0.25, eye_y - 8, W * 0.42, eye_y + 8, fill=eye_color, outline="")
        c.create_oval(W * 0.58, eye_y - 8, W * 0.75, eye_y + 8, fill=eye_color, outline="")
        # 瞳孔
        c.create_oval(W * 0.30, eye_y - 3, W * 0.37, eye_y + 3, fill="#003322", outline="")
        c.create_oval(W * 0.63, eye_y - 3, W * 0.70, eye_y + 3, fill="#003322", outline="")

        # 嘴 - LED网格
        expr = self._expression
        if expr == "happy":
            c.create_arc(W * 0.32, H * 0.50, W * 0.68, H * 0.65, start=0, extent=-180,
                         style="arc", outline=eye_color, width=2)
        elif expr == "surprised":
            c.create_oval(W * 0.38, H * 0.54, W * 0.62, H * 0.64,
                          fill=eye_color, outline="")
        else:
            c.create_line(W * 0.35, H * 0.58, W * 0.50, H * 0.62, fill=eye_color, width=2)
            c.create_line(W * 0.50, H * 0.62, W * 0.65, H * 0.58, fill=eye_color, width=2)

    def _draw_ghost(self):
        W, H = self._size, self._size
        c = self.canvas
        color = self.color
        eye_color = self._pet_cfg.get("eye_color", "#2C3E50")

        # 身体 - 上部圆下部波浪
        c.create_oval(W * 0.10, H * 0.05, W * 0.90, H * 0.60, fill=color, outline="")
        c.create_rectangle(W * 0.10, H * 0.35, W * 0.90, H * 0.72, fill=color, outline="")
        # 波浪底边
        wave_parts = [(0.10, 0.88, 0.80), (0.26, 0.94, 0.72), (0.42, 0.88, 0.85),
                      (0.58, 0.94, 0.72), (0.74, 0.88, 0.80), (0.90, 0.94, 0.72)]
        for x1, y1, y2 in wave_parts:
            c.create_arc(x1 * W, (y1 - 0.15) * H, (x1 + 0.16) * W, (y1 + 0.10) * H,
                         start=0, extent=180, fill=color, outline="")

        # 眼
        eye_y = H * 0.32
        c.create_oval(W * 0.26, eye_y - 8, W * 0.42, eye_y + 8, fill=eye_color, outline="")
        c.create_oval(W * 0.58, eye_y - 8, W * 0.74, eye_y + 8, fill=eye_color, outline="")
        c.create_oval(W * 0.29, eye_y - 3, W * 0.33, eye_y, fill="white", outline="")
        c.create_oval(W * 0.61, eye_y - 3, W * 0.65, eye_y, fill="white", outline="")

        # 嘴
        expr = self._expression
        if expr == "surprised":
            c.create_oval(W * 0.38, H * 0.44, W * 0.62, H * 0.52,
                          fill=eye_color, outline="")
        elif expr == "happy":
            c.create_arc(W * 0.35, H * 0.40, W * 0.65, H * 0.52, start=0, extent=-180,
                         style="arc", outline=eye_color, width=2)
        else:
            c.create_oval(W * 0.42, H * 0.44, W * 0.58, H * 0.52,
                          fill=eye_color, outline="")

    def _draw_penguin(self):
        W, H = self._size, self._size
        c = self.canvas
        color = self.color
        accent = self.accent_color
        eye_color = self._pet_cfg.get("eye_color", "#2C3E50")

        # 身体
        c.create_oval(W * 0.15, H * 0.10, W * 0.85, H * 0.95, fill="#2C3E50", outline="")
        # 白肚子
        c.create_oval(W * 0.25, H * 0.25, W * 0.75, H * 0.85, fill="white", outline="")

        # 翅膀
        c.create_oval(W * 0.02, H * 0.30, W * 0.20, H * 0.70, fill="#2C3E50", outline="")
        c.create_oval(W * 0.80, H * 0.30, W * 0.98, H * 0.70, fill="#2C3E50", outline="")

        # 眼
        blink = self._anim_frame % 120 > 115
        eye_y = H * 0.30
        if not blink:
            c.create_oval(W * 0.32, eye_y - 5, W * 0.44, eye_y + 5, fill=eye_color, outline="")
            c.create_oval(W * 0.56, eye_y - 5, W * 0.68, eye_y + 5, fill=eye_color, outline="")
            c.create_oval(W * 0.34, eye_y - 2, W * 0.37, eye_y + 1, fill="white", outline="")
            c.create_oval(W * 0.58, eye_y - 2, W * 0.61, eye_y + 1, fill="white", outline="")
        else:
            c.create_line(W * 0.30, eye_y, W * 0.46, eye_y, fill=eye_color, width=3)
            c.create_line(W * 0.54, eye_y, W * 0.70, eye_y, fill=eye_color, width=3)

        # 喙
        c.create_polygon(W * 0.42, H * 0.36, W * 0.50, H * 0.44,
                         W * 0.58, H * 0.36, fill=accent, outline="")

    # ---- 动画 ----
    def _start_anim(self):
        self._anim_active = True
        self._anim_loop()

    def _anim_loop(self):
        if not self._anim_active:
            return
        try:
            self._anim_frame += 1
            if self._anim_frame % 8 == 0:
                self.draw()

            # 随机微移（呼吸感）
            if self._behavior_cfg.get("idle_animations", True) and self._anim_frame % 60 == 0:
                speed = self._behavior_cfg.get("idle_speed", "normal")
                if speed == "active" and random.random() < 0.4:
                    dx = random.randint(-5, 5)
                    dy = random.randint(-3, 3)
                elif speed == "normal" and random.random() < 0.2:
                    dx = random.randint(-3, 3)
                    dy = random.randint(-2, 2)
                else:
                    dx, dy = 0, 0
                if dx or dy:
                    new_x = self.win.winfo_x() + dx
                    new_y = self.win.winfo_y() + dy
                    screen_w = self.win.winfo_screenwidth()
                    screen_h = self.win.winfo_screenheight()
                    new_x = max(0, min(new_x, screen_w - self._size))
                    new_y = max(0, min(new_y, screen_h - self._size))
                    self.win.geometry(f"+{new_x}+{new_y}")

            self.win.after(100, self._anim_loop)
        except tk.TclError:
            self._anim_active = False

    def stop_anim(self):
        self._anim_active = False

    # ---- 交互 ----
    def _on_drag_start(self, event):
        self._drag_x = event.x
        self._drag_y = event.y
        self.set_expression("surprised")

    def _on_drag_move(self, event):
        dx = event.x - self._drag_x
        dy = event.y - self._drag_y
        new_x = self.win.winfo_x() + dx
        new_y = self.win.winfo_y() + dy
        self.win.geometry(f"+{new_x}+{new_y}")

    def _on_enter(self, event):
        self.set_expression("happy")
        size = self._pet_cfg.get("size", 120)
        self.win.geometry(f"{size + 6}x{size + 6}+{self.win.winfo_x() - 3}+{self.win.winfo_y() - 3}")

    def _on_leave(self, event):
        self.set_expression("normal")
        size = self._pet_cfg.get("size", 120)
        self.win.geometry(f"{size}x{size}+{self.win.winfo_x() + 3}+{self.win.winfo_y() + 3}")

    def _handle_double_click(self):
        if self._on_double_click:
            self._on_double_click()

    def _handle_right_click(self):
        if self._on_right_click:
            self._on_right_click()

    def show_notification_bubble(self, text: str, duration=4000):
        """在宠物旁边显示对话气泡。"""
        bubble = tk.Toplevel(self.win)
        bubble.overrideredirect(True)
        bubble.wm_attributes("-topmost", True)
        bubble.config(bg="#FFF8DC")

        lbl = tk.Label(bubble, text=text, bg="#FFF8DC", fg="#333",
                       font=("Microsoft YaHei", 10), wraplength=200,
                       justify=tk.LEFT, padx=8, pady=6)
        lbl.pack()

        # 气泡打结
        canvas = tk.Canvas(bubble, width=16, height=12, bg="#FFF8DC", highlightthickness=0)
        canvas.create_polygon(0, 0, 16, 0, 8, 12, fill="#FFF8DC", outline="")
        canvas.pack()

        bubble.update_idletasks()
        x = self.win.winfo_x() + self._size // 2 - bubble.winfo_width() // 2
        y = self.win.winfo_y() - bubble.winfo_height() - 5
        bubble.geometry(f"+{x}+{y}")

        self.set_expression("thinking")
        bubble.after(duration, bubble.destroy)
        bubble.after(duration - 500, lambda: self.set_expression("normal"))
