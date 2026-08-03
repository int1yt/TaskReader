#!/usr/bin/env bash
# ============================================================
#  Tool-Android 一键安装脚本 (Termux)
#  用法:  bash install.sh               # 默认 qwen3:0.6b（小模型，任何手机可跑）
#  可选:  bash install.sh qwen3:1.7b    # 4GB+ 内存手机可换稍大的模型
#
#  零基础用户请看脚本底部的《手机端完整指引》。
#  已安装的步骤会自动跳过，可重复执行。
# ============================================================
set -euo pipefail

# ------------------------------------------------------------
#  环境检测：本脚本必须在 Termux 内运行。
#  若检测不到 Termux，则打印手机端完整指引后退出。
# ------------------------------------------------------------
IS_TERMUX=0
if [ -n "${TERMUX_VERSION:-}" ] || command -v termux-setup-storage >/dev/null 2>&1 \
   || [ -d "/data/data/com.termux" ]; then
  IS_TERMUX=1
fi

if [ "$IS_TERMUX" -eq 0 ]; then
  cat <<'GUIDE'

==============================================================================
   未检测到 Termux 环境！请先按下面的步骤在手机上安装 Termux：
==============================================================================

【第 1 步】在手机上安装两个应用（只需 3 分钟）
  1. 打开浏览器，访问  https://f-droid.org        （F-Droid 应用商店）
  2. 下载并安装 F-Droid
  3. 打开 F-Droid，搜索 "Termux"，点击安装
     （注意：不要从应用商店 / Play 商店安装，版本太旧会出错）

【第 2 步】把本 Tool-Android 文件夹拷贝到手机
  方法 A（推荐）：数据线连接电脑，把整个 Tool-Android 文件夹复制到
                  手机内部存储的 Download 目录下
  方法 B：用微信 / QQ 发送压缩包，在手机上解压

【第 3 步】打开 Termux，进入工具目录
  打开 Termux 后先输入下面这行（问权限就选允许）：
    termux-setup-storage
  然后输入（路径按你拷贝的位置改）：
    cd /storage/emulated/0/Download/Tool-Android

【第 4 步】一键安装（会自动装好一切）
    bash install.sh

  安装脚本会自动完成：更新软件源 → 装 Python → 装 Ollama →
  拉取小模型(qwen3:0.6b) → 写入配置文件。全程只需联网一次。

  装好后，随时用下面命令提取任务：
    bash run.sh 我下周三要交论文

==============================================================================
  如果哪一步卡住了，把报错信息截图发出来即可。
==============================================================================
GUIDE
  exit 1
fi

MODEL="${1:-qwen3:0.6b}"
cd "$(dirname "$0")"

step() { printf "\n==> %s\n" "$1"; }

echo ""
echo "=============================================================================="
echo "  Tool-Android 安装开始，全程自动，请耐心等待（首次需联网下载，约 1~2 分钟）"
echo "  模型: $MODEL"
echo "=============================================================================="

# ---------- 0. 存储权限 ----------
step "0/6 设置 Termux 存储访问权限"
if [ ! -d "$HOME/storage" ]; then
  echo "请在弹出的系统对话框中允许 Termux 访问存储。"
  termux-setup-storage 2>/dev/null || true
fi

# ---------- 1. 更新软件源 ----------
step "1/6 更新 Termux 软件源（首次较慢，请等待）"
pkg update -y
pkg upgrade -y

# ---------- 2. 安装 Python ----------
step "2/6 安装 Python"
pkg install -y python python-pip

# ---------- 3. 安装 Ollama（含 tur-repo）----------
step "3/6 安装 Ollama"
if ! command -v ollama >/dev/null 2>&1; then
  pkg install -y tur-repo || true
  pkg install -y ollama || pkg install -y ollama-termux || {
    echo "Ollama 安装失败。请先手动运行: pkg install tur-repo; pkg install ollama"
    exit 1
  }
fi
ollama --version || true

# ---------- 4. 安装 Python 依赖 ----------
step "4/6 安装 Python 依赖 (jieba)"
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ---------- 5. 启动服务 + 拉取小模型 ----------
step "5/6 启动 Ollama 服务并拉取模型 ($MODEL)"
# 模型存到 Termux 私有目录，避免 /sdcard 权限问题
export OLLAMA_MODELS="$HOME/.ollama/models"
if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "启动 Ollama 服务 ..."
  nohup ollama serve >/dev/null 2>&1 &
  sleep 5
fi
ollama pull "$MODEL"

# ---------- 6. 写配置 ----------
step "6/6 写入配置文件 task_reader/config.json"
cat > task_reader/config.json <<EOF
{"host": "http://127.0.0.1:11434", "model": "$MODEL"}
EOF

echo ""
echo "======================================================================"
echo "  安装完成！"
echo ""
echo "  以后每次使用，打开 Termux 输入："
echo "    cd /storage/emulated/0/Download/Tool-Android"
echo "    bash run.sh 我下周三要交论文"
echo ""
echo "  或只提取任务不联网（纯规则模式）："
echo "    bash run.sh '周五晚上八点开会' --no-llm"
echo "======================================================================"
