"""本地 LLM 通道：通过 Ollama HTTP API 调用，数据不出本机。

当 Ollama 未运行 / 未装模型 / 请求失败时，返回空结果，由规则层兜底。
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path

_DEFAULT_HOST = "http://127.0.0.1:11434"
_DEFAULT_MODEL = "qwen3:8b"

_CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def _load_config() -> dict:
    """读取包同级 config.json（由安装脚本生成）。不存在或损坏时返回空 dict。"""
    try:
        if _CONFIG_PATH.exists():
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


_CONFIG = _load_config()

_SYSTEM = (
    "你是任务提取助手。请从用户输入的中文句子中提取所有任务/计划，"
    "直接输出一个 JSON 数组（不要输出对象包装、不要 markdown 代码块、不要解释）。\n"
    "要求：句子可能包含多个任务（用逗号、然后、以及、顺便等连接），必须全部提取，一条都不能漏，也不要合并成一条。\n"
    "数组的每个元素是一个对象，必须只包含以下字段：\n"
    '1. "action": 动作/动词，字符串，如 "交"\n'
    '2. "object": 动作对象，字符串，没有则为空字符串\n'
    '3. "time_text": 原文中的时间短语，字符串，没有则为空字符串\n'
    '4. "date": 归一化日期 YYYY-MM-DD，以系统给的今天为基准换算相对时间，无法确定则为空字符串\n'
    '5. "time": 归一化时刻 HH:MM，没有则为空字符串\n'
    '6. "place": 地点，字符串，没有则为空字符串\n'
    '7. "notes": 附加信息/备注（如列表项内的补充说明），没有则为空字符串\n'
    '8. "confidence": 0 到 1 的置信度，数字\n'
    '示例：输入"我下周三要交论文，周五下午三点去图书馆"，今天为 2026-08-02，应输出：\n'
    '[{"action":"交","object":"论文","time_text":"下周三","date":"2026-08-05","time":"","place":"","confidence":0.95},'
    '{"action":"去","object":"图书馆","time_text":"周五下午三点","date":"2026-08-07","time":"15:00","place":"图书馆","confidence":0.9}]'
)

# 模型输出字段名到标准字段的映射（提高鲁棒性）
_FIELD_MAP = {
    "action": ("action", "verb", "task", "动作", "动词", "任务"),
    "object": ("object", "obj", "target", "对象", "内容"),
    "time_text": ("time_text", "time", "when", "时间", "时间短语", "原时间"),
    "date": ("date", "due_date", "deadline", "日期", "日期时间", "具体日期"),
    "time": ("time", "clock", "时刻"),
    "place": ("place", "location", "where", "地点", "位置"),
    "notes": ("notes", "note", "remark", "备注", "附加信息", "说明", "补充"),
    "confidence": ("confidence", "score", "置信度", "置信"),
}


def _pick(item: dict, key: str):
    for k in _FIELD_MAP.get(key, (key,)):
        if k in item and item[k] is not None:
            return item[k]
    return ""


class OllamaClient:
    def __init__(self, host: str = None, model: str = None, timeout: float = 300.0):
        import os
        self.host = (host
                     or os.environ.get("OLLAMA_HOST")
                     or _CONFIG.get("host")
                     or _DEFAULT_HOST)
        self.model = (model
                      or os.environ.get("TASK_READER_MODEL")
                      or _CONFIG.get("model")
                      or _DEFAULT_MODEL)
        self.timeout = timeout
        self._available = None

    def _check(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import urllib.request
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=2.0) as resp:
                data = json.loads(resp.read())
            names = [t.get("name", "") for t in data.get("models", [])]
            ok = any(self.model in n or n in self.model for n in names)
            self._available = ok
            if not ok:
                print(f"[llm] 未找到本地模型 {self.model}，可用: {names}", file=__import__("sys").stderr)
            return ok
        except Exception as e:
            print(f"[llm] Ollama 不可用（{e}），降级为纯规则模式。", file=__import__("sys").stderr)
            self._available = False
            return False

    def parse_tasks(self, sentence: str, ref_date: date):
        """解析整句中的任务。返回 list[dict]（部分字段可能为空）。"""
        if not self._check():
            return []

        user_msg = (
            f"今天日期：{ref_date.isoformat()}。\n"
            f"请提取下面句子中的任务并输出 JSON：\n{sentence}"
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0, "think": False},
        }
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self.host}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read())
            content = body.get("message", {}).get("content", "")
            return self._parse_json(content)
        except Exception as e:
            print(f"[llm] 请求失败：{e}", file=__import__("sys").stderr)
            return []

    @staticmethod
    def _extract_list(data):
        """从解析结果中取出任务列表：数组、对象包装、或单对象。"""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    return v
            return [data]
        return []

    @staticmethod
    def _parse_json(content: str):
        """从模型输出中容错地提取任务数组。"""
        content = content.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", content, re.S)
        if fence:
            content = fence.group(1).strip()

        data = None
        # 1) 直接整体解析
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # 2) 提取第一个 [ ... ] 段
            start, end = content.find("["), content.rfind("]")
            if start != -1 and end > start:
                data = _repair_json(content[start:end + 1])
            if not isinstance(data, list):
                # 3) 提取 { ... } 段
                start, end = content.find("{"), content.rfind("}")
                if start != -1 and end > start:
                    data = _repair_json(content[start:end + 1])

        items = OllamaClient._extract_list(data)
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue
            out.append({
                "action": str(_pick(item, "action") or "").strip(),
                "object": str(_pick(item, "object") or "").strip(),
                "time_text": str(_pick(item, "time_text") or "").strip(),
                "date": str(_pick(item, "date") or "").strip(),
                "time": str(_pick(item, "time") or "").strip(),
                "place": str(_pick(item, "place") or "").strip(),
                "notes": str(_pick(item, "notes") or "").strip(),
                "confidence": _to_float(_pick(item, "confidence"), 0.7),
            })
        return out


def _to_float(v, default=0.7):
    try:
        f = float(v)
        return min(max(f, 0.0), 1.0)
    except (TypeError, ValueError):
        return default


def _repair_json(text: str):
    """极端情况下修复残缺 JSON 的简单策略。"""
    try:
        return json.loads(text)
    except Exception:
        pass
    # 去掉行尾逗号等
    text = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(text)
    except Exception:
        return []
