"""地点抽取：词典 + 后缀模式。"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .task_model import PlaceSpan

_DICT_DIR = Path(__file__).parent / "dicts"
with open(_DICT_DIR / "places.json", encoding="utf-8") as f:
    _PLACES = json.load(f)

# 扁平化词典：多词条按长度降序，保证最长匹配优先
_PLACE_WORDS = sorted({w for cat in _PLACES.values() for w in cat}, key=len, reverse=True)


class PlaceParser:
    def parse(self, text: str):
        """返回 PlaceSpan 列表（按原文顺序，去重叠）。"""
        spans = []
        matched = set()
        for w in _PLACE_WORDS:
            for m in re.finditer(re.escape(w), text):
                if m.start() in matched:
                    continue
                spans.append(PlaceSpan(text=w, start=m.start(), end=m.end(), confidence=0.9))
                matched.add(m.start())
                break  # 每词最多取第一个出现，避免重复

        spans.sort(key=lambda s: (s.start, -(len(s.text))))
        out = []
        for s in spans:
            if out and s.start < out[-1].end:
                continue
            out.append(s)
        return out
