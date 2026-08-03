"""TaskReader 手机端测试客户端（模拟微信交互）。

通过手机浏览器访问 http://127.0.0.1:8000 ，用类似微信的聊天界面
测试任务提取核心流程。将来接入真实微信后，页面逻辑保持不变，
只是把 /api/chat 换成 wechat.adapter 的收发。

纯标准库实现，无额外依赖。用法:
  python webui.py              # 127.0.0.1:8000
  python webui.py --port 9000
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bot.core import BotCore  # noqa: E402

_HTML_DIR = Path(__file__).resolve().parent / "webui"

# 全局单例，Web 会话之间共享（后续微信端也复用同一个实例）
BOT = BotCore()


def _ref_today() -> str:
    return date.today().isoformat()


class Handler(BaseHTTPRequestHandler):
    server_version = "TaskReaderBot/1.0"

    # ---------- 工具 ----------
    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8", errors="replace"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def log_message(self, fmt, *args):  # 精简访问日志
        sys.stderr.write("[webui] %s\n" % (fmt % args))

    # ---------- 路由 ----------
    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            self._send_file("index.html")
        elif url.path == "/api/ping":
            self._send_json(200, {"ok": True, "ref": _ref_today(), "llm_ready": self._llm_ready()})
        else:
            self._send(404, b"not found")

    def do_POST(self):
        url = urlparse(self.path)
        if url.path == "/api/chat":
            self._handle_chat(self._read_json())
        else:
            self._send(404, b"not found")

    # ---------- 核心 ----------
    def _llm_ready(self) -> bool:
        try:
            from task_reader.llm import OllamaClient
            return bool(OllamaClient()._check())
        except Exception:
            return False

    def _handle_chat(self, args: dict):
        sentence = str(args.get("message", "")).strip()
        use_llm = bool(args.get("use_llm", True))
        if not sentence:
            self._send_json(400, {"error": "消息为空"})
            return
        try:
            reply = BOT.handle_text(sentence, use_llm=use_llm)
            payload = reply.to_dict()
            payload["ok"] = True
            payload["llm_ready"] = self._llm_ready()
            self._send_json(200, payload)
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"ok": False, "error": f"解析失败：{e}"})

    def _send_file(self, name: str):
        path = _HTML_DIR / name
        if not path.exists():
            self._send(404, b"not found")
            return
        self._send(200, path.read_bytes())


def main():
    ap = argparse.ArgumentParser(description="TaskReader 手机端测试客户端")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    print("=" * 60)
    print("  TaskReader 测试客户端已启动（模拟微信聊天）")
    print(f"  手机浏览器打开:  http://{args.host}:{args.port}")
    print("  数据仅在本机处理，不出手机。Ctrl+C 停止")
    print("=" * 60)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.server_close()


if __name__ == "__main__":
    main()
