#!/usr/bin/env bash
# ============================================================
#  Tool-Android 图形界面启动入口 (Termux)
#  启动本地 Web 服务，然后用手机浏览器打开图形界面。
#  用法:  bash serve.sh
#  可改端口:  bash serve.sh 9000
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

PORT="${1:-8000}"

# ---------- 环境检测 ----------
if [ -z "${TERMUX_VERSION:-}" ] && ! command -v termux-setup-storage >/dev/null 2>&1; then
  echo ""
  echo "请在手机上用 Termux 打开本工具："
  echo "  1. 安装 F-Droid，再从 F-Droid 安装 Termux"
  echo "  2. 打开 Termux，输入: cd /storage/emulated/0/Download/Tool-Android"
  echo "  3. 输入: bash install.sh"
  echo ""
  exit 1
fi

# ---------- 确保 Ollama 服务在运行（若启用 AI） ----------
if command -v ollama >/dev/null 2>&1; then
  if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "[serve] 启动 Ollama 服务 ..."
    export OLLAMA_MODELS="$HOME/.ollama/models"
    nohup ollama serve >/dev/null 2>&1 &
    sleep 5
  fi
fi

# ---------- 启动 Web 服务 ----------
echo ""
echo "[serve] 启动本地 Web 服务 ..."
python webui.py --host 127.0.0.1 --port "$PORT" &
SERVER_PID=$!
sleep 2

echo ""
echo "=============================================================================="
echo "  测试客户端已就绪！（模拟微信聊天，验证机器人核心流程）"
echo ""
echo "  请在手机浏览器打开:  http://127.0.0.1:$PORT"
echo ""
echo "  说明: 这是微信机器人的网页测试端。给机器人发一句话，"
echo "        它会像微信一样回复提取出的任务。"
echo "  停止:  在本窗口按 Ctrl+C，再输入:  kill $SERVER_PID"
echo "=============================================================================="

# 尝试自动打开浏览器（Termux 可用）
if command -v termux-open-url >/dev/null 2>&1; then
  termux-open-url "http://127.0.0.1:$PORT" 2>/dev/null || true
fi

wait $SERVER_PID
