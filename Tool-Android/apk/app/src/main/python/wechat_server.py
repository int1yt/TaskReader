"""微信公众平台服务器：接收微信消息并自动回复任务分类结果。

使用方式：
1. 注册微信个人订阅号（免费，mp.weixin.qq.com）
2. 手机开启热点，获取本机 IP
3. 安装内网穿透工具（如 cpolar / frp），将本机端口映射到公网
4. 公众号后台「开发 → 基本配置」填入公网 URL + Token
5. 启动本服务器

本模块由 Chaquopy 在 Android 上运行，监听本地端口。
收到微信消息 → 调用任务分类引擎 → 返回格式化回复。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.core import BotCore
from bot_config import load as load_config


class WeChatServer:
    def __init__(self, host="0.0.0.0", port=8080, token=""):
        self.host = host
        self.port = port
        self.token = token or "taskreader"
        self._server = None
        self._thread = None
        self._running = False
        self._core = BotCore()

    @property
    def running(self):
        return self._running

    def start(self):
        if self._running:
            return
        handler = self._make_handler()
        self._server = HTTPServer((self.host, self.port), handler)
        self._running = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        print(f"[wx_server] 公众号服务器已启动: {self.host}:{self.port}")

    def stop(self):
        self._running = False
        if self._server:
            self._server.shutdown()

    def _make_handler(self):
        token = self.token
        core = self._core

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                # 微信服务器验证 URL
                qs = self.path.split("?")[-1] if "?" in self.path else ""
                params = {}
                for p in qs.split("&"):
                    if "=" in p:
                        k, v = p.split("=", 1)
                        params[k] = v
                sig = params.get("signature", "")
                ts = params.get("timestamp", "")
                nonce = params.get("nonce", "")
                echostr = params.get("echostr", "")

                if self._check_sig(sig, ts, nonce):
                    self._ok(echostr)
                else:
                    self._ok("verify failed")

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                try:
                    root = ET.fromstring(body)
                    msg_type = root.find("MsgType")
                    if msg_type is not None and msg_type.text == "text":
                        from_user = root.find("FromUserName").text
                        to_user = root.find("ToUserName").text
                        content = root.find("Content").text

                        cfg = load_config()
                        use_llm = cfg.get("model", {}).get("use_llm", False)
                        reply_data = core.handle_text(content, use_llm=use_llm)
                        reply_text = reply_data.text

                        xml = self._build_reply(from_user, to_user, reply_text)
                        self._ok(xml)
                    else:
                        self._ok("success")
                except Exception:
                    self._ok("success")

            def _check_sig(self, sig, ts, nonce):
                try:
                    tmp = sorted([token, ts, nonce])
                    return hashlib.sha1("".join(tmp).encode()).hexdigest() == sig
                except Exception:
                    return False

            def _build_reply(self, to, from_, text):
                t = str(int(time.time()))
                return (
                    "<xml>"
                    f"<ToUserName><![CDATA[{to}]]></ToUserName>"
                    f"<FromUserName><![CDATA[{from_}]]></FromUserName>"
                    f"<CreateTime>{t}</CreateTime>"
                    "<MsgType><![CDATA[text]]></MsgType>"
                    f"<Content><![CDATA[{text}]]></Content>"
                    "</xml>"
                ).encode("utf-8")

            def _ok(self, body):
                self.send_response(200)
                self.send_header("Content-Type", "application/xml; charset=utf-8")
                self.end_headers()
                if isinstance(body, str):
                    body = body.encode("utf-8")
                self.wfile.write(body)

            def log_message(self, fmt, *args):
                pass  # 静默日志

        return Handler


# 全局单例
_server: WeChatServer | None = None


def start_server(host="0.0.0.0", port=8080, token=""):
    global _server
    if _server and _server.running:
        return {"ok": True, "msg": f"已在运行: {host}:{port}"}
    _server = WeChatServer(host=host, port=port, token=token)
    _server.start()
    return {"ok": True, "msg": f"已启动: {host}:{port}"}


def stop_server():
    global _server
    if _server:
        _server.stop()
        _server = None
    return {"ok": True}


def server_status():
    global _server
    if _server and _server.running:
        return {"ok": True, "running": True, "port": _server.port}
    return {"ok": True, "running": False}
