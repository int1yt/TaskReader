"""系统托盘图标与菜单 — 与桌宠模式集成。"""
from __future__ import annotations

import os
import sys

try:
    import pystray
    from PIL import Image, ImageDraw
    _HAS_TRAY = True
except ImportError:
    _HAS_TRAY = False


def _create_icon_image(size=64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(66, 133, 244, 255),
    )
    draw.text(
        (size // 2, size // 2), "T",
        fill=(255, 255, 255, 255),
        anchor="mm",
    )
    return img


class TrayApp:
    def __init__(self, app=None):
        self._app = app
        self._icon = None
        self._running = False

    @property
    def has_tray(self) -> bool:
        return _HAS_TRAY

    def run(self):
        if not _HAS_TRAY:
            print("pystray 未安装，运行在命令行模式。")
            print("输入 s 打开设置，t 任务清单，c 聊天，q 退出。")
            self._cmd_loop()
            return

        image = _create_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("聊天", self._action_chat),
            pystray.MenuItem("任务清单", self._action_tasks),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("设置", self._action_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._action_exit),
        )
        self._icon = pystray.Icon(
            "TaskReaderPet",
            image,
            "TaskReader 桌宠",
            menu,
        )
        self._icon.run()

    def _cmd_loop(self):
        while True:
            try:
                cmd = input("> ").strip().lower()
                if cmd == "s":
                    self._action_settings()
                elif cmd == "t":
                    self._action_tasks()
                elif cmd == "c":
                    self._action_chat()
                elif cmd == "q":
                    self._action_exit()
                    break
            except (EOFError, KeyboardInterrupt):
                break

    def _action_chat(self, icon=None, item=None):
        if self._app:
            self._app.chat.show()

    def _action_tasks(self, icon=None, item=None):
        if self._app:
            self._app.task_panel.show()

    def _action_settings(self, icon=None, item=None):
        from .settings import SettingsWindow
        if self._app:
            SettingsWindow(master=self._app.root, on_save=self._app._on_settings_saved)
        else:
            SettingsWindow()

    def _action_exit(self, icon=None, item=None):
        if self._app:
            self._app._exit_app()
        else:
            if self._icon and _HAS_TRAY:
                self._icon.stop()
                self._icon = None
            os._exit(0)

    def stop_tray(self):
        if self._icon and _HAS_TRAY:
            self._icon.stop()
            self._icon = None

    def notify(self, title: str, message: str):
        if self._icon and _HAS_TRAY:
            self._icon.notify(message, title)

    def update_title(self, status: str = ""):
        if self._icon and _HAS_TRAY:
            base = "TaskReader 桌宠"
            self._icon.title = f"{base} - {status}" if status else base
