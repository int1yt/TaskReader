#!/usr/bin/env bash
# Tool-Desktop 快捷运行入口 (macOS / Linux)
set -euo pipefail
cd "$(dirname "$0")"
if [ -x ".venv/bin/python" ]; then
  exec .venv/bin/python -m task_reader.cli "$@"
else
  exec python3 -m task_reader.cli "$@"
fi
