"""微信消息模型：适配器与 BotCore 之间的消息载体。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WeChatMessage:
    """一条微信消息。"""
    msg_id: Optional[str] = None
    from_user: Optional[str] = None
    to_user: Optional[str] = None
    content: str = ""
    type: str = "text"
    is_group: bool = False
    raw: object = None

    def __str__(self):
        who = self.from_user or "?"
        return f"[{who}] {self.content[:50]}"


@dataclass
class WeChatContext:
    """一次会话上下文：会话 id、用户资料、历史等。"""
    session_id: str = ""
    user_nickname: str = ""
    user_id: str = ""
    history: list = field(default_factory=list)
