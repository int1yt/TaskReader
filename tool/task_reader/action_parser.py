"""动作/宾语抽取：动词词典 + 句式模板 + jieba 兜底。"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .task_model import ActionSpan

_DICT_DIR = Path(__file__).parent / "dicts"
with open(_DICT_DIR / "verbs.json", encoding="utf-8") as f:
    _VERB_CATEGORIES = json.load(f)
with open(_DICT_DIR / "templates.json", encoding="utf-8") as f:
    _TEMPLATES = json.load(f)

# 动词 → 规范动作
_VERB_CANON = {}
for cat, verbs in _VERB_CATEGORIES.items():
    for v in verbs:
        _VERB_CANON[v] = cat

# 按长度降序，长动词优先（如"打电话"优于"打"）
_VERB_SORTED = sorted(_VERB_CANON, key=len, reverse=True)

_INTENT = _TEMPLATES["意图标记"]
_INTENT_SORTED = sorted(_INTENT, key=len, reverse=True)
_INTENT_RE = re.compile("|".join(re.escape(w) for w in _INTENT_SORTED))

# 宾语截断边界（含半角/全角标点、连接词、虚词）
_BOUNDARY = ",.;:!?()[]<>，。！？；：、和以及还并然后再同时也要等就都很"

_CRAP = {"了", "着", "过", "要", "得", "吧", "呢", "啊", "哦", "嗯", "很", "就", "都"}


def _seg(tokens):
    try:
        import jieba.posseg as pseg
        return [(w.word, w.flag) for w in pseg.cut("".join(tokens))]
    except Exception:
        return []


# 动词后面紧跟这些字时，多半是名词的一部分（如"打印机""打印店"），应跳过
_VERB_NOUN_SUFFIX = {"打印": "机店室纸墨"}


def _token_start_flags(text: str):
    """返回 {词起始偏移: (词, 词性)}。用于校验动词匹配是否落在真实词边界上。"""
    try:
        import jieba.posseg as pseg
        out = {}
        off = 0
        for x in pseg.cut(text):
            w, flag = x.word, x.flag
            if w and not w.isspace():
                out.setdefault(off, (w, flag))
            off += len(w)
        return out
    except Exception:
        return {}


def _verb_forms(text: str):
    """返回所有命中动词的 (动词, 起始索引, 规范类别, 置信度)。

    用 jieba 词边界 + 词性校验，避免"打印机"里的"打印"、"装修"里的"修"被误判为动词；
    同时允许"见面"这类被 jieba 标为名词但本身即词典动词的情况。
    """
    flags = _token_start_flags(text)
    found = []
    for v in _VERB_SORTED:
        excl = _VERB_NOUN_SUFFIX.get(v, "")
        for m in re.finditer(re.escape(v), text):
            i = m.start()
            if excl and m.end() < len(text) and text[m.end()] in excl:
                continue
            tok = flags.get(i)
            if tok is None:
                continue  # 动词不在词边界上（如"装修"里的"修"）
            word, flag = tok
            if len(v) == 1 and word != v:
                continue  # 单字动词必须正好是独立词（避免"记得"里的"记"、"看见"里的"看"）
            if flag.startswith("n") and word != v:
                continue  # 该位置是其它名词词（如"打印机"里的"打印"）
            conf = 0.85 if len(v) >= 2 else 0.8
            found.append((v, i, _VERB_CANON[v], conf))
    return found


def _pre_object(text: str, verb_start: int, time_spans, place_spans, verb_starts=()):
    """动词前置宾语（"一期大创申报"）：取时间/地点之后的文本作为宾语。

    当前置文本里还有其它动词（如"看完网课记笔记"里"记笔记"前面是另一动作），
    或只剩"要"等助词时，不当作宾语。
    """
    content_start = 0
    for s in sorted(list(time_spans) + list(place_spans), key=lambda s: s.start):
        if s.end <= verb_start and s.start >= content_start:
            content_start = s.end
            if getattr(s, "is_deadline", False):
                for m in ("之前", "以前", "截止", "截止到", "截至", "以内", "之内"):
                    if text[content_start:content_start + len(m)] == m:
                        content_start += len(m)
                        break
    pre = text[content_start:verb_start].strip(" ，,。、")
    if not pre:
        return ""
    if any(content_start <= s < verb_start for s in verb_starts):
        return ""
    pre = pre.strip("".join(_CRAP))
    return pre if pre else ""


def _extract_object(text: str, verb_end: int, time_spans, place_spans, verb="",
                    next_verb_start=None):
    """提取动词的宾语：优先识别"把/将 X + 动词"句式，否则取动词后名词短语。"""
    if verb:
        ba = re.search(rf"把(?P<obj>[^把，。！？；、\s]{{1,10}}){re.escape(verb)}", text[:verb_end])
        if ba:
            obj = ba.group("obj")
            if obj:
                return obj.strip()

    start = verb_end
    # 跳过助词/意图词（"要"除外：它是宾语与附加要求的边界，如"发消息要电话号码"）
    while start < len(text) and text[start] in _CRAP and text[start] != "要":
        start += 1
    if start >= len(text):
        return ""

    # 动词后的时间/地点（如"准备明天英语Quiz"里夹着的"明天"）应跳过而非截断宾语
    spans = sorted([s for s in list(time_spans) + list(place_spans) if s.end > verb_end],
                   key=lambda s: s.start)
    while True:
        moved = False
        for s in spans:
            if s.start == start:
                start = s.end
                moved = True
        if not moved:
            break
    if start >= len(text):
        return ""

    # 确定边界位置（时间/地点/标点/连接词/下一个动词）
    stops = [len(text)]
    for s in spans:
        if s.start >= start:
            stops.append(s.start)
    for m in re.finditer(r"[%s]" % re.escape(_BOUNDARY), text):
        if m.start() >= start:
            stops.append(m.start())
    if next_verb_start is not None and next_verb_start >= start:
        stops.append(next_verb_start)
    stop = min(stops)

    raw_obj = text[start:stop].strip()
    if not raw_obj:
        return ""

    # 用 jieba 截取名词部分，去掉尾部虚词/结构助词
    obj = raw_obj
    try:
        import jieba.posseg as pseg
        words = [(w.word, w.flag) for w in pseg.cut(raw_obj)]
        kept = []
        for w, flag in words:
            if flag.startswith(("n", "v")) or w not in _CRAP:
                kept.append(w)
        if kept:
            obj = "".join(kept).strip()
    except Exception:
        pass
    return obj


class ActionParser:
    def parse(self, text: str, time_spans=(), place_spans=()):
        """返回 ActionSpan 列表。"""
        results = []

        # 0) 过滤位于时间范围内的动词（如"2:00到4:00"里的"到"），并按位置排序
        range_spans = [s for s in time_spans if getattr(s, "granularity", "") == "range"]
        verb_forms = sorted(
            [vf for vf in _verb_forms(text)
             if not any(s.start <= vf[1] < s.end for s in range_spans)],
            key=lambda vf: vf[1],
        )

        # 1) 词典动词
        verb_starts = {vf[1] for vf in verb_forms}
        for idx, (v, i, canon, conf) in enumerate(verb_forms):
            next_start = verb_forms[idx + 1][1] if idx + 1 < len(verb_forms) else None
            obj = _extract_object(text, i + len(v), time_spans, place_spans, v, next_start)
            if not obj:
                obj = _pre_object(text, i, time_spans, place_spans, verb_starts)
            conf = min(1.0, conf + (0.05 if obj else 0))
            results.append(ActionSpan(
                text=text[i:i + len(v)], start=i, end=i + len(v),
                confidence=conf, action=v, object=obj, canonical=canon,
            ))

        # 2) 意图标记后、且词典未命中任何动词时，用 jieba 识别动词短语
        if results:
            results.sort(key=lambda s: (s.start, -len(s.text)))
            out = []
            for s in results:
                if out and s.start < out[-1].end:
                    # 重叠时保留更长的动作（如"交作业" vs "交"）
                    if len(s.text) > len(out[-1].text):
                        out[-1] = s
                    continue
                out.append(s)
            return out

        _AUX = {"是", "有", "要", "会", "能", "可以", "帮", "让", "请", "给",
                "把", "叫", "使", "将", "被", "想", "希望", "需要"}
        for m in _INTENT_RE.finditer(text):
            seg = text[m.end():]
            if not seg:
                continue
            tokens = _seg(seg)
            for idx, (w, flag) in enumerate(tokens):
                if flag.startswith("v") and w not in _AUX:
                    # 找到第一个动词后停止
                    i = m.end() + sum(len(t[0]) for t in tokens[:idx])
                    verb_end = i + len(w)
                    obj = _extract_object(text, verb_end, time_spans, place_spans, w)
                    results.append(ActionSpan(
                        text=w, start=i, end=verb_end,
                        confidence=0.6, action=w, object=obj,
                        canonical=_VERB_CANON.get(w, "其他"),
                    ))
                    break

        if not results:
            return []

        results.sort(key=lambda s: (s.start, -len(s.text)))
        out = []
        for s in results:
            if out and s.start < out[-1].end:
                # 重叠时保留更长的动作（如"交作业" vs "交"）
                if len(s.text) > len(out[-1].text):
                    out[-1] = s
                continue
            out.append(s)
        return out
