"""微信适配器：基于 wxauto 的 Windows 微信机器人。"""
from __future__ import annotations

import json
import sys
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from task_reader.engine import TaskReader
from task_reader.llm import OllamaClient
from app.config import load_config
from wechat.models import WeChatMessage


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


class WeChatAdapter:
    """微信机器人适配器：监听消息 → 任务分类 → 自动回复。"""

    def __init__(self):
        self._reader = TaskReader()
        self._running = False
        self._thread = None
        self._wx = None
        self._config = load_config()
        self._ollama = None

    @property
    def running(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            return
        self._config = load_config()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._running = True
        self._thread.start()

    def stop(self):
        self._running = False

    def _ensure_wechat(self):
        if self._wx is not None:
            # wxauto 内部已有重连，返回即可
            try:
                self._wx.GetSessionList()
                return self._wx
            except Exception:
                self._wx = None
        try:
            from wxauto import WeChat
            self._wx = WeChat()
            print("[wechat] 已连接到微信客户端")
            return self._wx
        except ImportError:
            print("[wechat] wxauto 未安装，请运行: pip install wxauto")
            return None
        except Exception as e:
            print(f"[wechat] 连接微信失败: {e}")
            return None

    def _get_messages(self):
        wx = self._wx
        if wx is None:
            return {}
        cfg = self._config.get("bot", {})
        try:
            if cfg.get("listen_all", True):
                return wx.GetAllMessage() or {}
            else:
                listen_list = cfg.get("listen_list", [])
                for who in listen_list:
                    wx.AddListenChat(who)
                return wx.GetListenMessage() or {}
        except Exception:
            return {}

    def _format_reply(self, tasks: list) -> str:
        cfg = self._config
        profile = cfg.get("bot_profile", {})
        style = cfg.get("reply_style", {})

        if not tasks:
            return style.get("no_task", "没有识别到任务，换个说法试试？")

        emoji = style.get("use_emoji", False)
        header = style.get("task_header", "收到！为你整理了 {count} 个任务：")
        header = header.format(count=len(tasks))
        if emoji:
            header = header.replace("收到", "📨 收到").replace("任务", "任务 📋")

        lines = [header]
        for i, t in enumerate(tasks, 1):
            name = t.get("task") or t.get("raw") or "任务"
            item_fmt = style.get("task_item",
                                 "{index}. {name}\n   时间：{time}\n   备注：{note}")
            item = item_fmt.format(
                index=str(i),
                name=name,
                time=_fmt_time(t) or "未指定",
                note=_fmt_note(t) or "无",
            )
            lines.append(item)

        footer = style.get("task_footer", "")
        if footer:
            lines.append(footer)

        if profile.get("signature", False):
            name = profile.get("name", "小读")
            lines.append(f"\n—— {name}")

        return "\n".join(lines)

    def _process_message(self, who: str, content: str, is_self: bool = False):
        cfg = self._config
        bot_cfg = cfg.get("bot", {})

        if is_self and not bot_cfg.get("reply_to_self", False):
            return None

        content = content.strip()
        if not content:
            return None

        model_cfg = cfg.get("model", {})
        use_llm = model_cfg.get("use_llm", False)

        try:
            tasks = self._reader.parse_json(content, use_llm=use_llm)
        except Exception:
            traceback.print_exc()
            return "抱歉，处理消息时出错了，请稍后再试。"

        return self._format_reply(tasks)

    def _loop(self):
        print("[wechat] 机器人已启动，等待微信连接...")
        while self._running:
            try:
                wx = self._ensure_wechat()
                if wx is None:
                    time.sleep(5)
                    continue

                msgs = self._get_messages()
                if not msgs:
                    time.sleep(1)
                    continue

                for chat_name, msg_list in msgs.items():
                    if not msg_list:
                        continue
                    for msg in msg_list:
                        if not isinstance(msg, (list, tuple)) or len(msg) < 2:
                            continue
                        sender = str(msg[0]) if len(msg) > 0 else ""
                        content = str(msg[1]) if len(msg) > 1 else ""
                        is_self = len(msg) > 2 and str(msg[2]) == "self"

                        reply = self._process_message(sender, content, is_self)
                        if reply:
                            try:
                                wx.SendMsg(reply, who=chat_name)
                                print(f"[wechat] 回复 {chat_name}: {reply[:50]}...")
                            except Exception as e:
                                print(f"[wechat] 发送失败: {e}")
                time.sleep(1)
            except Exception:
                traceback.print_exc()
                time.sleep(3)

        print("[wechat] 机器人已停止")


def dry_run(sentence: str = "我下周三要交论文，周五下午三点去图书馆还书"):
    adapter = WeChatAdapter()
    reply = adapter._format_reply(
        adapter._reader.parse_json(sentence, use_llm=False)
    )
    print("=" * 50)
    print("输入:", sentence)
    print("-" * 50)
    print(reply)
    print("=" * 50)
    return reply


if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        args = [a for a in sys.argv[1:] if a != "--dry-run"]
        dry_run(args[0] if args else None)
    else:
        adapter = WeChatAdapter()
        adapter.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            adapter.stop()
