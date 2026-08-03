"""交互式聊天测试端（Termux 命令行，不用 HTTP / 浏览器）。

像微信一样一问一答：输入一句话，机器人回复提取出的任务。
与网页端、微信端共用同一个 BotCore，验证的是同一套核心逻辑。

用法:
  python -m bot.chat                # 默认 AI 增强
  python -m bot.chat --no-llm       # 纯规则模式（更快，不依赖 Ollama）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.core import BotCore  # noqa: E402

BOT = BotCore()

WELCOME = """
==========================================================
  TaskReader 交互测试端（模拟微信聊天）
  输入一句话，回车后看机器人回复。输入 quit / 退出 结束。
==========================================================
"""


def _banner():
    print(WELCOME)
    # 尝试检测 LLM 是否可用
    try:
        from task_reader.llm import OllamaClient
        ok = OllamaClient()._check()
        print(f"  本地 AI 模型: {'可用' if ok else '不可用（将自动降级为纯规则）'}")
    except Exception:
        print("  本地 AI 模型: 未知")
    print("=" * 58)


def chat_loop(use_llm: bool = True):
    _banner()
    while True:
        try:
            line = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出")
            break
        if not line:
            continue
        if line in ("quit", "退出", "q", "exit"):
            print("已退出")
            break

        reply = BOT.handle_text(line, use_llm=use_llm)
        print("-" * 58)
        print("机器人:")
        print(reply.text)
        print("-" * 58)


def main():
    use_llm = "--no-llm" not in sys.argv
    chat_loop(use_llm=use_llm)


if __name__ == "__main__":
    main()
