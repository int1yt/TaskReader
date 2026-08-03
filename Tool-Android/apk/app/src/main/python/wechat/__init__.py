"""微信模块（预留）。

目标：把 TaskReader 做成微信个人号机器人，用户直接给微信好友发一句话，
机器人回复提取出的任务。

当前状态：接口已预留（wechat/adapter.py + wechat/models.py），
真实登录/收发待接入微信 SDK 后实现。先用网页测试端（bash serve.sh）
验证核心流程。

接入 TODO：
  1. 选定微信 SDK（如 itchat / wechaty / wxauto / 企业微信回调）
  2. 在 WeChatAdapter.login() 实现登录
  3. 在 WeChatAdapter._on_message() 里把 SDK 消息转成 WeChatMessage
  4. 在 WeChatAdapter.send() 里把 Reply.text 发回给用户
"""
from .adapter import WeChatAdapter
from .models import WeChatMessage, WeChatContext

__all__ = ["WeChatAdapter", "WeChatMessage", "WeChatContext"]
