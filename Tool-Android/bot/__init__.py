"""bot：任务机器人核心（与传输无关）。

- core.BotCore      处理一条文本消息，返回 Reply（文本 + 结构化任务）
- reply.Reply       机器人输出统一格式

网页端、微信端都复用 BotCore，业务逻辑只写一次。
"""
from .core import BotCore
from .reply import Reply

__all__ = ["BotCore", "Reply"]
