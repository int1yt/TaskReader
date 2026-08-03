"""分句：支持整段描述与结构化列表（1. 2. 3.）两种输入。"""
from __future__ import annotations

import json
import re
from pathlib import Path

_DICT_DIR = Path(__file__).parent / "dicts"

with open(_DICT_DIR / "templates.json", encoding="utf-8") as f:
    _TEMPLATES = json.load(f)

_CONJUNCTIONS = _TEMPLATES["并列连接词"]

# 连接词排序：长词优先，避免把"还有"拆成"还"
_CONJUNCTIONS_SORTED = sorted(_CONJUNCTIONS, key=len, reverse=True)
_CONJ_RE = re.compile("|".join(re.escape(c) for c in _CONJUNCTIONS_SORTED))

# 标点切分（整段描述模式）。注意：不含 ":"（时刻/头部）和 "."（小数/序号）避免误拆
_PUNCT_RE = re.compile(r"[,;!?<>\[\]()\s。]+")

# 结构化列表序号（紧贴式）：1. 1、 1) 1． 允许前面紧贴汉字，如"网课2."（前面非数字，避免 3.14/1.5 误拆）
_LIST_ITEM_GLUED = re.compile(r"(?<!\d)\d+[.、．)]\s*")
# 结构化列表序号（分隔式）：,2, 或 开头 1, —— 顿号/半角逗号归一后，逗号作分隔仅当前面是分隔符，
# 避免"3个,5个"这类数量枚举误判为列表
_LIST_ITEM_SEP = re.compile(r"(?:(?<=^)|(?<=[,，。;；\s]))\d+,\s*")

# 头部时间上下文：今天任务： / 周五下午： （冒号前非数字，避免 "2:00" 里的冒号误判）
_HEADER_RE = re.compile(r"^(.+?)(?<!\d)[:：]")
_TASK_WORD = ("任务", "计划", "安排", "待办", "日程", "清单", "备忘")


def _list_markers(text: str):
    """返回所有列表序号匹配（去重、按位置排序）。"""
    ms = list(_LIST_ITEM_GLUED.finditer(text)) + list(_LIST_ITEM_SEP.finditer(text))
    ms.sort(key=lambda m: m.start())
    return ms


def is_structured(text: str) -> bool:
    """是否结构化列表输入（含 1. 2. 3. 序号）。"""
    return bool(_list_markers(text))


def _segment_plain(text: str):
    parts = []
    buf = ""
    start = 0
    i = 0
    n = len(text)
    while i < n:
        m = _CONJ_RE.match(text, i)
        if m:
            if buf.strip():
                parts.append((buf.strip(), start))
            buf = ""
            start = i + len(m.group(0))
            i = start
            continue
        ch = text[i]
        if _PUNCT_RE.fullmatch(ch):
            if buf.strip():
                parts.append((buf.strip(), start))
            buf = ""
            start = i + 1
        else:
            buf += ch
        i += 1
    if buf.strip():
        parts.append((buf.strip(), start))
    return parts


def _segment_structured(text: str):
    """结构化列表：按 序号 切分，保留项内逗号（一个序号 = 一条任务）。"""
    parts = []
    last = 0
    for m in _list_markers(text):
        seg = text[last:m.start()].strip("，,。 \t")
        if seg:
            parts.append((seg, last))
        last = m.end()
    tail = text[last:].strip("，,。 \t")
    if tail:
        parts.append((tail, last))
    return parts


def segment(text: str):
    """将整句切成若干子句，返回 [(子句文本, 起始偏移)]。"""
    if not text:
        return []
    if is_structured(text):
        return _segment_structured(text)
    return _segment_plain(text)


def extract_header(text: str):
    """提取头部时间上下文。

    形如"今天任务：""周五下午："：返回 (去掉头部的剩余文本, 头部文本, 是否为任务标题)。
    若头部是"任务/计划/安排"类标题，其时间作为整批任务的默认时间。
    """
    m = _HEADER_RE.match(text)
    if not m:
        return text, "", False
    prefix = m.group(1).strip()
    is_title = any(w in prefix for w in _TASK_WORD)
    return text[m.end():].lstrip(), prefix, is_title
