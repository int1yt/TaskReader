"""消息回复模型：机器人对外输出统一格式。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Reply:
    """机器人对一条消息的回复。

    text  : 发送给用户的纯文本（微信/网页通用）
    tasks : 结构化任务列表（JSON 数组，供富文本前端或后续扩展使用）
    """
    text: str
    tasks: list = field(default_factory=list)
    source: str = "rule"           # rule | llm | hybrid
    confidence: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "tasks": self.tasks,
            "source": self.source,
            "confidence": self.confidence,
        }
