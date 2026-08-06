"""提醒系统：后台轮询任务到期时间，弹出提醒。"""
from __future__ import annotations

import threading
import time
from datetime import datetime

from .config import load_config, LANG_STRINGS


class Reminder:
    def __init__(self, task_panel=None, pet_window=None):
        self._task_panel = task_panel
        self._pet_window = pet_window
        self._cfg = load_config()
        self._running = False
        self._thread = None
        self._notified = set()

    @property
    def running(self):
        return self._running

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def refresh_config(self):
        self._cfg = load_config()

    def _loop(self):
        while self._running:
            try:
                self._check_reminders()
            except Exception:
                pass
            time.sleep(30)

    def _check_reminders(self):
        reminder_cfg = self._cfg.get("reminder", {})
        if not reminder_cfg.get("enabled", True):
            return
        if not self._task_panel:
            return

        lang = self._cfg.get("language", {}).get("ui_lang", "zh")
        strings = LANG_STRINGS.get(lang, LANG_STRINGS["zh"])
        pet_name = self._cfg.get("bot_profile", {}).get("name", "小读")

        advance_mins = reminder_cfg.get("advance_minutes", 30)
        advance_1h = reminder_cfg.get("advance_hours_1", 1)
        advance_24h = reminder_cfg.get("advance_hours_2", 24)

        for mins in [advance_mins, advance_1h * 60, advance_24h * 60]:
            tasks = self._task_panel.get_upcoming_tasks(mins)
            for task, diff in tasks:
                task_id = task.get("id", "")
                key = f"{task_id}_{mins}"
                if key in self._notified:
                    continue
                self._notified.add(key)

                task_name = task.get("task") or task.get("raw", "任务")
                task_time = task.get("time") or task.get("time_end", "")
                if not task_time:
                    task_time = task.get("time_text", "即将到期")

                if mins <= 60:
                    body = strings["reminder_body"].format(
                        name=pet_name, task=task_name, time=task_time)
                elif mins <= 1440:
                    body = f"{pet_name}：提醒你，「{task_name}」还有约{mins // 60}小时到期~"
                else:
                    body = f"{pet_name}：提醒你，「{task_name}」明天到期，提前准备哦~"

                if self._pet_window:
                    try:
                        self._pet_window.show_notification_bubble(body)
                    except Exception:
                        pass
