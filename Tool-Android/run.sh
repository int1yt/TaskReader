#!/usr/bin/env bash
# ============================================================
#  Tool-Android 快捷运行入口 (Termux)
#  自动拉起 Ollama 服务（若未运行）后解析任务。
#  用法:  bash run.sh 我下周三要交论文
#         bash run.sh '明天任务：1.看网课 2.做作业' --no-llm
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

if [ -z "${TERMUX_VERSION:-}" ] && ! command -v termux-setup-storage >/dev/null 2>&1; then
  echo ""
  echo "请先在手机上用 Termux 打开本工具："
  echo "  1. 安装 F-Droid，再从 F-Droid 安装 Termux"
  echo "  2. 打开 Termux，输入: cd /storage/emulated/0/Download/Tool-Android"
  echo "  3. 输入: bash install.sh"
  echo ""
  exit 1
fi

# 确保 Ollama 服务在运行
if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "[run] 启动 Ollama 服务 ..."
  export OLLAMA_MODELS="$HOME/.ollama/models"
  nohup ollama serve >/dev/null 2>&1 &
  sleep 5
fi

exec python -m task_reader.cli "$@"
