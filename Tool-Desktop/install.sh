#!/usr/bin/env bash
# ============================================================
#  Tool-Desktop 一键安装脚本 (macOS / Linux)
#  用法:  bash install.sh                # 默认 qwen3:8b
#  可选:  bash install.sh qwen3:4b       # 显式指定模型
#  已安装的步骤会自动跳过，可重复执行。
# ============================================================
set -euo pipefail
MODEL="${1:-qwen3:8b}"
cd "$(dirname "$0")"

step() { printf "\n==> %s\n" "$1"; }

# ---------- 1. Python ----------
step "1/5 检查 Python"
if ! command -v python3 >/dev/null 2>&1; then
  echo "未检测到 python3，请先安装 Python 3.10+ 后重试。"
  echo "  macOS:   brew install python"
  echo "  Debian:  sudo apt install python3 python3-venv"
  exit 1
fi
python3 --version

# ---------- 2. 虚拟环境 + 依赖 ----------
step "2/5 创建虚拟环境并安装依赖 (jieba)"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

# ---------- 3. Ollama ----------
step "3/5 检查 Ollama"
if ! command -v ollama >/dev/null 2>&1; then
  echo "未检测到 Ollama，正在安装 ..."
  if [[ "$(uname)" == "Darwin" ]]; then
    brew install ollama
  else
    curl -fsSL https://ollama.com/install.sh | sh
  fi
fi
ollama --version

# ---------- 4. 启动服务 + 拉取模型 ----------
step "4/5 启动 Ollama 服务并拉取模型 ($MODEL)"
if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "启动 Ollama 服务 ..."
  nohup ollama serve >/dev/null 2>&1 &
  sleep 4
fi
ollama pull "$MODEL"

# ---------- 5. 写配置 ----------
step "5/5 写入配置文件 task_reader/config.json"
cat > task_reader/config.json <<EOF
{"host": "http://127.0.0.1:11434", "model": "$MODEL"}
EOF

echo ""
echo "安装完成！使用方法:"
echo "  .venv/bin/python -m task_reader.cli '我下周三要交论文'"
echo "  ./run.sh '我下周三要交论文'"
