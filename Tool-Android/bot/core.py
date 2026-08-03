"""机器人核心：与传输无关（不依赖微信/网页）。

任何入口（微信、网页、命令行）都调用 BotCore.handle_text()，
由它负责：解析文本 → 生成任务 → 组装回复文本。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from task_reader.engine import TaskReader  # noqa: E402

from .reply import Reply  # noqa: E402


def _fmt_time(t: dict) -> str:
    ts, te = t.get("time_start"), t.get("time_end")
    if ts and te and ts != te:
        s = f"{ts} ~ {te}"
    else:
        s = t.get("time") or ""
    txt = (t.get("time_text") or "").strip()
    return s + (f"（{txt}）" if txt else "")


def _fmt_note(t: dict) -> str:
    parts = []
    if t.get("place"):
        parts.append(t["place"])
    if t.get("notes"):
        parts.append(t["notes"])
    return "；".join(parts)


def _build_text(sentence: str, tasks: list) -> str:
    """把任务列表渲染成发给用户的纯文本。"""
    if not tasks:
        return "没有识别到任务，换个说法试试？\n（可勾选「使用 AI」增强识别）"
    lines = [f"好的，为你找到 {len(tasks)} 个任务："]
    for i, t in enumerate(tasks, 1):
        name = t.get("task") or t.get("raw") or "任务"
        lines.append(f"{i}. {name}")
        if _fmt_time(t):
            lines.append(f"   时间：{_fmt_time(t)}")
        if _fmt_note(t):
            lines.append(f"   备注：{_fmt_note(t)}")
        conf = t.get("confidence")
        if conf:
            lines.append(f"   置信度：{conf:.0%}")
    return "\n".join(lines)


class BotCore:
    def __init__(self, ref=None, model: Optional[str] = None, host: Optional[str] = None):
        self._model = model
        self._host = host
        self._ref = ref
        self._reader = None

    @property
    def reader(self) -> TaskReader:
        if self._reader is None:
            self._reader = TaskReader(ref=self._ref)
        return self._reader

    def handle_text(self, sentence: str, use_llm: bool = True) -> Reply:
        """处理一条用户文本消息，返回回复。"""
        if not sentence or not sentence.strip():
            return Reply(text="请发一句包含任务的话给我，例如：明天下午三点去图书馆还书。")

        tasks = self.reader.parse_json(sentence, use_llm=use_llm)
        text = _build_text(sentence, tasks)

        # 统计来源与置信度（供日志/统计）
        sources = {t.get("source", "rule") for t in tasks}
        confs = [t.get("confidence") for t in tasks if t.get("confidence") is not None]
        return Reply(
            text=text,
            tasks=tasks,
            source=("/".join(sorted(sources)) if sources else "rule"),
            confidence=max(confs) if confs else None,
        )

    def handle_text_tasks(self, sentence: str, use_llm: bool = True) -> list:
        """仅返回结构化任务列表（JSON），供网页前端直接渲染卡片。"""
        if not sentence or not sentence.strip():
            return []
        return self.reader.parse_json(sentence, use_llm=use_llm)

    def handle_text_json(self, sentence: str, use_llm: bool = True) -> str:
        """返回 Reply 的 JSON 字符串，供 Android WebView 桥接调用。"""
        reply = self.handle_text(sentence, use_llm=use_llm)
        data = reply.to_dict()
        data["ok"] = True
        return json.dumps(data, ensure_ascii=False)
