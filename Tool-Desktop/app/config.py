"""机器人配置管理：加载/保存 bot 个性化设置。"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("TASKREADER_CONFIG",
                Path.home() / ".taskreader"))
CONFIG_FILE = CONFIG_DIR / "bot_config.json"

DEFAULT_CONFIG = {
    "bot_profile": {
        "name": "小读",
        "nickname": "TaskReader助手",
        "personality": "friendly",
        "tone": "casual",
        "signature": True,
    },
    "reply_style": {
        "task_header": "收到！为你整理了 {count} 个任务：",
        "task_item": "{index}. {name}\n   时间：{time}\n   备注：{note}",
        "task_footer": "有需要随时找我~",
        "no_task": "没有识别到任务，换个说法试试？",
        "use_emoji": False,
    },
    "model": {
        "host": "http://127.0.0.1:11434",
        "model": "qwen3:0.6b",
        "use_llm": False,
    },
    "bot": {
        "auto_start": False,
        "listen_all": True,
        "listen_list": [],
        "reply_to_self": False,
    },
    "pet_appearance": {
        "style": "cat",
        "color": "#FF8C00",
        "accent_color": "#FF6347",
        "eye_color": "#2C3E50",
        "size": 120,
        "always_on_top": True,
        "opacity": 0.95,
    },
    "pet_behavior": {
        "idle_animations": True,
        "greeting_on_start": True,
        "react_to_messages": True,
        "idle_speed": "normal",
        "auto_hide_taskbar": True,
    },
    "reminder": {
        "enabled": True,
        "advance_minutes": 30,
        "advance_hours_1": 1,
        "advance_hours_2": 24,
        "sound_enabled": True,
        "popup_duration": 10,
    },
    "language": {
        "ui_lang": "zh",
        "use_traditional": False,
    },
}

PERSONALITIES = {
    "friendly": "友好亲切",
    "professional": "专业严谨",
    "casual": "轻松随意",
    "concise": "简洁高效",
    "cute": "活泼可爱",
}

PET_STYLES = {
    "cat": "小猫",
    "dog": "小狗",
    "rabbit": "兔子",
    "robot": "机器人",
    "ghost": "小幽灵",
    "penguin": "企鹅",
}

LANGUAGES = {
    "zh": "简体中文",
    "zh-TW": "繁體中文",
    "en": "English",
    "ja": "日本語",
}

BEHAVIOR_PATTERNS = {
    "normal": "标准",
    "lazy": "慵懒",
    "active": "活泼",
}

LANG_STRINGS = {
    "zh": {
        "title": "TaskReader 桌宠",
        "settings": "设置",
        "task_list": "任务清单",
        "chat": "聊天",
        "reminder_title": "任务提醒",
        "reminder_body": "{name}，你的任务「{task}」将在 {time} 到期，抓紧时间哦~",
        "no_tasks": "暂无任务",
        "task_done": "已完成",
        "task_pending": "待完成",
        "save": "保存",
        "cancel": "取消",
        "reset": "恢复默认",
        "start": "启动",
        "stop": "停止",
        "exit": "退出",
    },
    "zh-TW": {
        "title": "TaskReader 桌寵",
        "settings": "設定",
        "task_list": "任務清單",
        "chat": "聊天",
        "reminder_title": "任務提醒",
        "reminder_body": "{name}，你的任務「{task}」將在 {time} 到期，抓緊時間哦~",
        "no_tasks": "暫無任務",
        "task_done": "已完成",
        "task_pending": "待完成",
        "save": "儲存",
        "cancel": "取消",
        "reset": "還原預設",
        "start": "啟動",
        "stop": "停止",
        "exit": "退出",
    },
    "en": {
        "title": "TaskReader Desktop Pet",
        "settings": "Settings",
        "task_list": "Task List",
        "chat": "Chat",
        "reminder_title": "Task Reminder",
        "reminder_body": "{name}, your task \"{task}\" is due at {time}, hurry up~",
        "no_tasks": "No tasks",
        "task_done": "Done",
        "task_pending": "Pending",
        "save": "Save",
        "cancel": "Cancel",
        "reset": "Reset",
        "start": "Start",
        "stop": "Stop",
        "exit": "Exit",
    },
    "ja": {
        "title": "TaskReader デスクトップペット",
        "settings": "設定",
        "task_list": "タスクリスト",
        "chat": "チャット",
        "reminder_title": "タスクリマインダー",
        "reminder_body": "{name}、タスク「{task}」は {time} に期限です、急いでね〜",
        "no_tasks": "タスクなし",
        "task_done": "完了",
        "task_pending": "未完了",
        "save": "保存",
        "cancel": "キャンセル",
        "reset": "リセット",
        "start": "起動",
        "stop": "停止",
        "exit": "終了",
    },
}


def load_config() -> dict:
    cfg = deepcopy(DEFAULT_CONFIG)
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                _deep_merge(cfg, data)
    except Exception:
        pass
    return cfg


def save_config(cfg: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
