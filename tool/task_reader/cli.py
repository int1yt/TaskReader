"""命令行入口。

用法:
  python -m task_reader.cli "我下周三要交论文"
  python -m task_reader.cli "我下周三要交论文" --ref 2026-08-02 --no-llm
  python -m task_reader.cli "..." --model qwen3:4b
  echo "句子" | python -m task_reader.cli --stdin
"""
from __future__ import annotations

import argparse
import json
import sys

from .engine import TaskReader


def _build_parser():
    p = argparse.ArgumentParser(
        prog="task_reader",
        description="从中文自然语句中提取任务/计划",
    )
    p.add_argument("sentence", nargs="?", help="要解析的句子")
    p.add_argument("--ref", default=None, help="参考日期 YYYY-MM-DD（默认今天），用于换算相对时间")
    p.add_argument("--no-llm", action="store_true", help="禁用本地LLM，仅用规则")
    p.add_argument("--model", default=None, help="Ollama 模型名（默认 qwen3:8b）")
    p.add_argument("--stdin", action="store_true", help="从标准输入读取句子")
    p.add_argument("--pretty", action="store_true", help="美化 JSON 输出")
    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    if args.model:
        import os
        os.environ["TASK_READER_MODEL"] = args.model

    sentences = []
    if args.stdin or (not args.sentence and not sys.stdin.isatty()):
        for line in sys.stdin:
            line = line.strip()
            if line:
                sentences.append(line)
    elif args.sentence:
        sentences.append(args.sentence)
    else:
        _build_parser().print_help()
        return 1

    reader = TaskReader(ref=args.ref)
    results = []
    for s in sentences:
        results.extend(reader.parse_json(s, use_llm=not args.no_llm))

    out = json.dumps(results, ensure_ascii=False, indent=2 if args.pretty else None)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
