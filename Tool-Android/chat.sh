#!/usr/bin/env bash
# ============================================================
#  Tool-Android 交互聊天测试端（Termux 命令行，不用 HTTP/浏览器）
#  像微信一样一问一答，验证机器人核心流程。
#  用法:  bash chat.sh                 # AI 增强
#         bash chat.sh --no-llm        # 纯规则（更快）
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

if [ -z "${TERMUX_VERSION:-}" ] && ! command -v termux-setup-storage >/dev/null 2>&1; then
  echo ""
  echo "请在手机上用 Termux 打开本工具："
  echo "  1. 安装 F-Droid，再从 F-Droid 安装 Termux"
  echo "  2. 打开 Termux，输入: cd /storage/emulated/0/Download/Tool-Android"
  echo "  3. 输入: bash install.sh"
  echo ""
  exit 1
fi

# 若用了 AI 模式，确保 Ollama 服务在运行
USE_LLM=1
for a in "$@"; do
  if [ "$a" = "--no-llm" ]; then USE_LLM=0; fi
done

if [ "$USE_LLM" -eq 1 ] && command -v ollama >/dev/null 2>&1; then
  if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "[chat] 启动 Ollama 服务 ..."
    export OLLAMA_MODELS="$HOME/.ollama/models"
    nohup ollama serve >/dev/null 2>&1 &
    sleep 5
  fi
fi

if [ "$USE_LLM" -eq 1 ]; then
  python -m bot.chat
else
  python -m bot.chat --no-llm
fi
