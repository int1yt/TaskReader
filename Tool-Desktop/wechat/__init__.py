"""微信机器人模块：消息模型 + 适配器。"""
from .models import WeChatMessage, WeChatContext
from .adapter import WeChatAdapter

__all__ = ["WeChatMessage", "WeChatContext", "WeChatAdapter"]
