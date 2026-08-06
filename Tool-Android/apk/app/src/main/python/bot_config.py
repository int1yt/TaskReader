"""机器人个性配置管理：供 WebView 桥接读写。
数据存储在 App 私有目录，卸载时自动删除。
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path


def _get_config_dir() -> Path:
    # Android 上使用 App 私有 files 目录（卸载时自动清除）
    try:
        from com.chaquo.python import Python
        app = Python.getPlatform().getApplication()
        return Path(app.getFilesDir().getAbsolutePath()) / "config"
    except Exception:
        pass
    # 桌面测试回退到环境变量或用户目录
    return Path(os.environ.get("TASKREADER_CONFIG",
                Path(os.path.expanduser("~")) / ".taskreader"))


_CONFIG_DIR = _get_config_dir()
_CONFIG_FILE = _CONFIG_DIR / "bot_config.json"

DEFAULT = {
    "bot_profile": {
        "name": "小读",
        "nickname": "任务助手",
        "wechat_id": "taskreader_bot",
        "avatar_color": "#07c160",
        "avatar_text": "读",
        "avatar_path": "",
        "bio": "帮你把日常对话变成结构化任务",
        "status": "随时随地，分解任务",
        "personality": "friendly",
        "tone": "casual",
        "signature": True,
    },
    "reply_style": {
        "header": "收到！为你整理了 {count} 个任务：",
        "item": "{index}. {name}\n   ⏰ {time}\n   📍 {note}",
        "footer": "有需要随时找我~",
        "no_task": "没有识别到任务，换个说法试试？",
        "use_emoji": True,
    },
    "model": {
        "host": "http://127.0.0.1:11434",
        "model": "qwen3:0.6b",
        "use_llm": False,
    },
    "system": {
        "language": "zh",
        "wechat_self_name": "",
        "trigger_keyword": "/task",
    },
}

PERSONALITIES = ["friendly", "professional", "casual", "concise", "cute"]
PERSONALITY_NAMES = {
    "friendly": "友好亲切",
    "professional": "专业严谨",
    "casual": "轻松随意",
    "concise": "简洁高效",
    "cute": "活泼可爱",
}

# 按个性 + 语言定义回复模板
PERSONALITY_TEMPLATES = {
    "friendly": {
        "zh": {
            "header": "收到！帮你整理了 {count} 个任务哦~",
            "item": "{index}. {name}\n   ⏰ {time}\n   📍 {note}",
            "footer": "随时找我，一起把任务搞定！",
            "no_task": "嗯...好像没有识别到任务呢，换个说法试试？",
        },
        "en": {
            "header": "Got it! I've organized {count} task(s) for you:",
            "item": "{index}. {name}\n   Time: {time}\n   Place: {note}",
            "footer": "Feel free to reach out anytime!",
            "no_task": "Hmm... I couldn't identify any tasks. Try rephrasing?",
        },
    },
    "professional": {
        "zh": {
            "header": "任务分解完毕，共 {count} 项：",
            "item": "{index}. {name}\n   时间：{time}\n   地点/备注：{note}",
            "footer": "以上为本次解析结果。",
            "no_task": "未能识别有效任务，请提供更明确的任务描述。",
        },
        "en": {
            "header": "Task analysis complete, {count} item(s):",
            "item": "{index}. {name}\n   Time: {time}\n   Location/Notes: {note}",
            "footer": "End of analysis.",
            "no_task": "No valid task identified. Please provide a clearer description.",
        },
    },
    "casual": {
        "zh": {
            "header": "搞定！{count} 个任务安排上了：",
            "item": "{index}. {name}\n   {time}\n   {note}",
            "footer": "加油干就完了~",
            "no_task": "没找到任务，你是不是忘了说干啥了？",
        },
        "en": {
            "header": "Sorted! {count} task(s) lined up:",
            "item": "{index}. {name}\n   {time}\n   {note}",
            "footer": "Go get 'em!",
            "no_task": "No tasks found. Did you forget to mention what to do?",
        },
    },
    "concise": {
        "zh": {
            "header": "{count}个任务：",
            "item": "{index}. {name} | {time} | {note}",
            "footer": "",
            "no_task": "未识别到任务。",
        },
        "en": {
            "header": "{count} task(s):",
            "item": "{index}. {name} | {time} | {note}",
            "footer": "",
            "no_task": "No tasks.",
        },
    },
    "cute": {
        "zh": {
            "header": "叮咚~ 小读帮你整理好啦，{count} 个任务喵！",
            "item": "{index}. {name}\n   ⏰ {time}\n   📍 {note}",
            "footer": "一起加油鸭~ (๑•̀ㅂ•́)و✧",
            "no_task": "唔...好像没有找到任务呢，再说说看？",
        },
        "en": {
            "header": "Ding dong~ I've organized {count} task(s) for you! ☆",
            "item": "{index}. {name}\n   Time: {time}\n   Place: {note}",
            "footer": "You can do it! (◕‿◕)ノ",
            "no_task": "Hmm... no tasks found, wanna try again?",
        },
    },
}


def get_personality_templates(personality: str = None, language: str = None) -> dict:
    """根据个性和语言返回回复模板。找不到时回退到 friendly + zh。"""
    pd = PERSONALITIES[0] if personality not in PERSONALITY_TEMPLATES else personality
    lang = language if language in ("zh", "en") else "zh"
    templates = PERSONALITY_TEMPLATES.get(pd, PERSONALITY_TEMPLATES["friendly"])
    return templates.get(lang, templates["zh"])


def load() -> dict:
    cfg = deepcopy(DEFAULT)
    try:
        if _CONFIG_FILE.exists():
            data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                _deep_merge(cfg, data)
    except Exception:
        pass
    return cfg


def save(cfg: dict):
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_json() -> str:
    return json.dumps(load(), ensure_ascii=False)


def save_json(json_str: str) -> bool:
    try:
        save(json.loads(json_str))
        return True
    except Exception:
        return False


def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
