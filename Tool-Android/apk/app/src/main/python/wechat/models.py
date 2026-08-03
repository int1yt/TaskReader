"""微信消息模型：适配器与 BotCore 之间的消息载体（预留）。

将来接入真实微信 SDK（如 itchat / wechaty / wxauto 等）时，
把收到的微信消息转换成 WeChatMessage，再交给 BotCore 处理。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WeChatMessage:
    """一条微信消息（预留，字段按需扩展）。"""
    msg_id: Optional[str] = None        # 微信消息 ID
    from_user: Optional[str] = None     # 发送者（微信号/群名）
    to_user: Optional[str] = None       # 接收者（机器人自身）
    content: str = ""                   # 文本内容（图文消息取文本部分）
    type: str = "text"                  # text | image | ... 
    is_group: bool = False              # 是否群消息
    raw: object = None                  # 原始 SDK 消息对象

    def __str__(self):
        who = self.from_user or "?"
        return f"[{who}] {self.content[:50]}"


@dataclass
class WeChatContext:
    """一次会话上下文（预留）：会话 id、用户资料、历史等。"""
    session_id: str = ""
    user_nickname: str = ""
    user_id: str = ""
    history: list = field(default_factory=list)   # 最近 N 条 (msg, reply)
