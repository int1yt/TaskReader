"""主引擎：分句 → 规则抽取 → 本地LLM → 融合与置信度评分。"""
from __future__ import annotations

import json
from datetime import date, datetime

from .normalize import normalize
from .segment import extract_header, is_structured, segment
from .time_parser import TimeParser
from .place_parser import PlaceParser
from .action_parser import ActionParser
from .llm import OllamaClient
from .task_model import Task


def _pick_ref(ref=None):
    if ref is None:
        return date.today()
    if isinstance(ref, datetime):
        return ref.date()
    if isinstance(ref, str):
        return datetime.strptime(ref, "%Y-%m-%d").date()
    return ref


def _nearest(anchor_start: int, anchor_end: int, spans, used):
    """在 spans 中找距 anchor 最近的未使用项，返回 (span, index)。"""
    best, best_idx, best_d = None, -1, None
    for i, s in enumerate(spans):
        if i in used:
            continue
        d = min(abs(s.start - anchor_end), abs(s.start - anchor_start))
        if best_d is None or d < best_d:
            best, best_idx, best_d = s, i, d
    return best, best_idx


_LIGHT_VERBS = {"去", "来", "到", "前往", "出发", "回", "赴", "前去", "赶往", "返回"}


def _dedupe_verbs(xs):
    """合并同一动词短语产生的多个动作候选：优先实义动词，动词含于另一动词时保留更长者。"""
    if not xs:
        return xs
    content = [x for x in xs if x.action not in _LIGHT_VERBS]
    if content:
        xs = content
    out = []
    for x in xs:
        if any(x.action != y.action and x.action in y.action for y in xs):
            continue
        out.append(x)
    return out


def _rule_tasks(text: str, ref: date):
    """对单个子句做规则抽取，返回 (Task列表, time_spans, place_spans, action_spans)。"""
    tp, pp, ap = TimeParser(ref), PlaceParser(), ActionParser()
    ts, ps = tp.parse(text), pp.parse(text)
    xs = ap.parse(text, ts, ps)
    xs = _dedupe_verbs(xs)

    tasks = []
    if not xs:
        # 无明确动词：仍保留时间/地点信息（不吞信息）
        conf = 0.5
        time, time_start, time_end = _time_fields(ts[0]) if ts else (None, None, None)
        t = Task(
            task=text,
            time_text=" ".join(s.text for s in ts),
            time=time,
            time_start=time_start,
            time_end=time_end,
            place=" ".join(s.text for s in ps),
            raw=text, confidence=conf, source="rule",
        )
        if ts or ps:
            t.confidence = max(0.5, max([s.confidence for s in ts] + [0.0]) * 0.6,
                               max([s.confidence for s in ps] + [0.0]) * 0.6)
        tasks.append(t)
        return tasks, ts, ps, xs

    used_t = set()
    used_p = set()
    for x in xs:
        t, ti = _nearest(x.start, x.end, ts, used_t)
        p, pi = _nearest(x.start, x.end, ps, used_p)
        if ti != -1:
            used_t.add(ti)
        if pi != -1:
            used_p.add(pi)

        conf = x.confidence
        if t is not None:
            conf = min(1.0, conf * 0.5 + t.confidence * 0.5 + 0.05)
        if p is not None:
            conf = min(1.0, conf * 0.7 + p.confidence * 0.3 + 0.03)

        time, time_start, time_end = _time_fields(t)
        task = Task(
            action=x.action,
            object=x.object,
            task=x.action + x.object,
            time_text=t.text if t else "",
            time=time,
            time_start=time_start,
            time_end=time_end,
            place=p.text if p else "",
            raw=text,
            confidence=round(conf, 3),
            source="rule",
        )
        tasks.append(task)
    return tasks, ts, ps, xs


def _fmt_time(t):
    if t is None:
        return None
    if t.time:
        return f"{t.date} {t.time}"
    return t.date


def _time_fields(t):
    """从 TimeSpan 生成 (time, time_start, time_end) 三元组。"""
    if t is None:
        return None, None, None
    if t.granularity == "range":
        date = t.date
        start = f"{date} {t.time_start}" if t.time_start else date
        end = f"{date} {t.time_end}" if t.time_end else date
        return start, start, end
    base = _fmt_time(t)
    if t.is_deadline:
        # 截止时间：只有结束界，无起始界
        return base, None, base
    return base, base, base


def _join_time(ts):
    """多个时间跨度时给出主时间（优先截止时间/完整日期）。"""
    if not ts:
        return None
    ts = sorted(ts, key=lambda s: (-int(s.is_deadline), -len(s.text)))
    return _fmt_time(ts[0])


def _match_score(rt: Task, lt: dict):
    s = 0
    if rt.action and lt["action"] and (rt.action in lt["action"] or lt["action"] in rt.action):
        s += 2
    if rt.object and lt["object"] and (rt.object in lt["object"] or lt["object"] in rt.object):
        s += 2
    if rt.place and lt["place"] and rt.place == lt["place"]:
        s += 2
    if rt.time_text and lt["time_text"] and (rt.time_text in lt["time_text"] or lt["time_text"] in rt.time_text):
        s += 1
    if rt.raw and (lt["action"] in rt.raw or lt["object"] in rt.raw):
        s += 1
    return s


def _merge(rt: Task, lt: dict):
    """规则任务与 LLM 任务融合，字段互补。"""
    time = rt.time or (lt["date"] and lt["time"] and f"{lt['date']} {lt['time']}"
                       or lt["date"] or None)
    conf = min(1.0, 0.5 * rt.confidence + 0.5 * lt["confidence"] + 0.05)
    merged = Task(
        action=rt.action or lt["action"],
        object=rt.object or lt["object"],
        task=rt.task or (lt["action"] and lt["object"] and lt["action"] + lt["object"]) or rt.raw,
        time_text=rt.time_text or lt["time_text"],
        time=time,
        time_start=rt.time_start or time,
        time_end=rt.time_end or time,
        place=rt.place or lt["place"],
        notes=rt.notes or lt.get("notes", ""),
        raw=rt.raw,
        confidence=round(conf, 3),
        source="hybrid",
    )
    return merged


def _merge_item_tasks(tasks):
    """结构化列表项内部合并为单任务：首个动作为主任务，其余作为 notes。"""
    if not tasks or len(tasks) <= 1:
        return tasks
    primary = tasks[0]
    extra = []
    for t in tasks[1:]:
        part = (t.action + t.object) if t.action else t.raw
        if part and part not in extra:
            extra.append(part)
    primary.notes = "，".join(extra)
    return [primary]


def _parse_all(text: str, ref: date, use_llm: bool,
               default_time=None, default_time_text=""):
    client = OllamaClient() if use_llm else None
    if client is not None and not client._check():
        client = None

    structured = is_structured(text)
    all_tasks = []
    for seg_text, off in segment(text):
        tasks, ts, ps, xs = _rule_tasks(seg_text, ref)

        # 结构化模式下合并列表项内部为单任务 + 附加信息
        if structured and len(tasks) > 1:
            tasks = _merge_item_tasks(tasks)

        # 头部上下文时间作为缺失时间的默认值
        if default_time:
            for t in tasks:
                if not t.time:
                    t.time = default_time
                    t.time_start = t.time_start or default_time
                    t.time_end = t.time_end or default_time
                    if not t.time_text:
                        t.time_text = default_time_text

        # LLM 兜底：仅当规则层没有识别出动作时调用（规则已覆盖则零开销、秒出）
        if client is not None and not any(x.action for x in xs):
            llm_tasks = [it for it in client.parse_tasks(seg_text, ref)
                         if it["action"] or it["time_text"] or it["place"]]
        else:
            llm_tasks = []

        if not llm_tasks:
            all_tasks.extend(tasks)
            continue

        merged = []
        used_rule = set()
        for lt in llm_tasks:
            best, best_score, best_idx = None, 0, -1
            for i, rt in enumerate(tasks):
                if i in used_rule:
                    continue
                sc = _match_score(rt, lt)
                if sc > best_score:
                    best, best_score, best_idx = rt, sc, i
            if best is not None and best_score >= 2:
                used_rule.add(best_idx)
                merged.append(_merge(best, lt))
            else:
                time = (lt["date"] and lt["time"] and f"{lt['date']} {lt['time']}"
                        or lt["date"] or None)
                merged.append(Task(
                    action=lt["action"], object=lt["object"],
                    task=(lt["action"] + lt["object"]) if lt["action"] else seg_text,
                    time_text=lt["time_text"],
                    time=time, time_start=time, time_end=time,
                    place=lt["place"], notes=lt.get("notes", ""), raw=seg_text,
                    confidence=round(lt["confidence"], 3),
                    source="llm",
                ))
        for i, rt in enumerate(tasks):
            if i not in used_rule:
                merged.append(rt)
        all_tasks.extend(merged)

    return all_tasks


class TaskReader:
    def __init__(self, ref=None):
        self.ref = _pick_ref(ref)

    def parse(self, sentence: str, use_llm: bool = True):
        """解析一句话，返回 Task 列表。"""
        if not sentence or not sentence.strip():
            return []
        text = normalize(sentence.strip())
        rest, header, is_title = extract_header(text)
        default_time, default_time_text = None, ""
        if header:
            # 头部时间上下文（如"今天任务："中的"今天"）作为整批任务的默认时间
            ts = TimeParser(self.ref).parse(header)
            if ts:
                default_time = _join_time(ts)
                default_time_text = " ".join(s.text for s in ts)
        tasks = _parse_all(rest, self.ref, use_llm,
                           default_time=default_time,
                           default_time_text=default_time_text)
        return tasks

    def parse_json(self, sentence: str, use_llm: bool = True):
        return [t.to_dict() for t in self.parse(sentence, use_llm=use_llm)]
