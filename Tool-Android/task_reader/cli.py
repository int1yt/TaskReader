"""命令行入口。

用法:
  python -m task_reader.cli "我下周三要交论文"            # 终端交互时输出表格
  python -m task_reader.cli "我下周三要交论文" --json     # 强制 JSON
  python -m task_reader.cli "..." --ref 2026-08-02 --no-llm
  python -m task_reader.cli "..." --model qwen3:4b
  echo "句子" | python -m task_reader.cli --stdin         # 管道/脚本默认 JSON
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata

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
    p.add_argument("--table", action="store_true", help="强制表格输出（终端交互时默认）")
    p.add_argument("--json", action="store_true", help="强制 JSON 输出")
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

    if args.table or (not args.json and sys.stdout.isatty()):
        print(_render_table(results))
    else:
        out = json.dumps(results, ensure_ascii=False, indent=2 if args.pretty else None)
        print(out)
    return 0


def _disp_width(s: str) -> int:
    """显示宽度：中文等全角字符按 2 列计。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def _pad(s: str, width: int) -> str:
    return s + " " * max(0, width - _disp_width(s))


def _disp_time(t: dict) -> str:
    ts, te = t.get("time_start"), t.get("time_end")
    if ts and te and ts != te:
        s = f"{ts} ~ {te}"
    else:
        s = t.get("time") or ""
    txt = (t.get("time_text") or "").strip()
    return s + (f"（{txt}）" if txt else "")


def _disp_note(t: dict) -> str:
    parts = []
    if t.get("place"):
        parts.append(t["place"])
    if t.get("notes"):
        parts.append(t["notes"])
    return "；".join(parts)


def _render_table(results) -> str:
    if not results:
        return "（无任务）"
    header = ("序号", "任务", "时间", "备注")
    rows = [
        (str(i + 1), t.get("task") or t.get("raw") or "",
         _disp_time(t), _disp_note(t))
        for i, t in enumerate(results)
    ]
    widths = [max(_disp_width(header[c]), max(_disp_width(r[c]) for r in rows))
              for c in range(4)]
    lines = [
        "  ".join(_pad(header[c], widths[c]) for c in range(4)),
        "  ".join("-" * widths[c] for c in range(4)),
    ]
    for r in rows:
        lines.append("  ".join(_pad(r[c], widths[c]) for c in range(4)))
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
