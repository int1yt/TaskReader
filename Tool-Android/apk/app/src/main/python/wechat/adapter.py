"""微信接入适配器（预留接口，尚未实现真实登录/收发）。

这是将来接入真实微信的唯一入口。需要实现：
  1. login()          —— 扫码/登录微信
  2. _on_message()    —— 收到微信消息的回调
  3. send()           —— 发送消息给用户

实现者只需把收到的微信消息转成 wechat.models.WeChatMessage，
调用 self.core.handle_text() 得到 Reply，再 send() 回去即可。
所有业务逻辑都在 bot.core.BotCore 中，微信端不需要关心解析细节。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.core import BotCore  # noqa: E402
from bot.reply import Reply  # noqa: E402
from .models import WeChatMessage  # noqa: E402


class WeChatAdapter:
    """微信机器人适配器（预留骨架）。

    当前仅打通接口与流程，login/_on_message/send 三处为 TODO，
    待选定微信 SDK 后实现。命令行 `python -m wechat.adapter --dry-run`
    可无微信环境模拟一条消息走完整流程。
    """

    def __init__(self, core: BotCore = None):
        self.core = core or BotCore()

    # ------------------------------------------------------------------
    # TODO(实现): 登录 / 收发
    # ------------------------------------------------------------------
    def login(self):
        """登录微信并进入监听循环。待实现（itchat/wechaty 等）。"""
        raise NotImplementedError("微信登录尚未实现，请先使用网页测试端：bash serve.sh")

    def send(self, to_user: str, reply: Reply):
        """发送消息给用户。待实现。"""
        raise NotImplementedError("微信发送尚未实现")

    def _on_message(self, msg: WeChatMessage):
        """收到微信消息（由具体 SDK 回调调用）。"""
        reply = self.core.handle_text(msg.content, use_llm=True)
        self.send(msg.from_user or msg.to_user, reply)
        return reply

    # ------------------------------------------------------------------
    # 测试：无微信环境时验证整个流程
    # ------------------------------------------------------------------
    def dry_run(self, sentence: str = "我下周三要交论文，周五下午三点去图书馆把书还了"):
        msg = WeChatMessage(msg_id="dry", from_user="test", content=sentence)
        reply = self.core.handle_text(msg.content, use_llm=True)
        print("=" * 50)
        print("收到消息:", msg)
        print("-" * 50)
        print(reply.text)
        print("-" * 50)
        print("结构化任务数:", len(reply.tasks))
        print("=" * 50)
        return reply


def main():
    import sys as _sys
    args = [a for a in _sys.argv[1:] if not a.startswith("--")]
    sentence = args[0] if args else "我下周三要交论文，周五下午三点去图书馆把书还了"
    WeChatAdapter().dry_run(sentence)


if __name__ == "__main__":
    main()
