"""主引擎：分句 → 规则抽取 → 本地LLM兜底。"""
from __future__ import annotations

import json
from datetime import date, datetime, time

from .normalize import normalize
from .segment import extract_header, is_structured, segment
from .time_parser import TimeParser, _DEADLINE_MARKERS
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

_LEAD = sorted(["别忘了", "记得要", "记得", "我们", "一起", "顺便", "帮我", "需要",
                "打算", "计划", "还要", "要", "在", "有", "我"] + list(_LIGHT_VERBS),
               key=len, reverse=True)


def _span_eff_end(text: str, s) -> int:
    """时间/地点跨度的有效结束位置：截止时间把紧跟的"之前/以前"等标记一并吞掉。"""
    e = s.end
    if getattr(s, "is_deadline", False):
        for m in _DEADLINE_MARKERS:
            if text[e:e + len(m)] == m:
                e += len(m)
                break
        if text[e:e + 1] == "前" and text[e:e + 2] != "前往":
            e += 1
    return e


def _strip_spans_sub(text: str, start: int, spans) -> str:
    """从 text 中移除 start 之后各 span 覆盖（含截止标记）的文本，返回剩余。"""
    out = []
    pos = start
    for s in sorted(spans, key=lambda s: s.start):
        if s.start < pos or s.end <= pos:
            continue
        if s.start > pos:
            out.append(text[pos:s.start])
        pos = max(pos, _span_eff_end(text, s))
    if pos < len(text):
        out.append(text[pos:])
    return "".join(out)


def _strip_lead(name: str) -> str:
    """剥离任务名开头的语气/谓词词。"""
    name = name.strip(" ，,。、")
    changed = True
    while changed and name:
        changed = False
        for w in _LEAD:
            if name.startswith(w) and len(name) > len(w):
                name = name[len(w):].strip(" ，,。、")
                changed = True
                break
    return name


def _action_end(text: str, x) -> int:
    """动作跨度结束位置：含宾语（宾语在动词之后时）。"""
    end = x.end
    if x.object:
        pos = text.find(x.object, x.end)
        if pos != -1:
            end = max(end, pos + len(x.object))
    return end


def _task_fields(text: str, ts, ps, xs):
    """构造 (任务名, 备注)。单动词时任务名=原文去掉时间/地点，尾部的"要X"作为备注。"""
    spans = list(ts) + list(ps)
    if not xs:
        name = _strip_lead(_strip_spans_sub(text, 0, spans))
        if not name:
            name = text.strip()
        return name, ""
    if len(xs) == 1:
        full = _strip_spans_sub(text, 0, spans)
        notes = _strip_spans_sub(text, _action_end(text, xs[0]), spans).strip(" ，,。、")
        if notes and (notes.startswith("要") or notes.startswith("需要")):
            if full.endswith(notes):
                full = full[:len(full) - len(notes)].strip(" ，,。、")
        else:
            notes = ""
        name = _strip_lead(full)
        if not name:
            name = text.strip()
        return name, notes
    return None, None


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


def _rule_tasks(text: str, ref: date, now: datetime = None, context_date: date = None):
    """对单个子句做规则抽取，返回 (Task列表, time_spans, place_spans, action_spans)。"""
    tp, pp, ap = TimeParser(ref, now=now, context_date=context_date), PlaceParser(), ActionParser()
    ts, ps = tp.parse(text), pp.parse(text)
    xs = ap.parse(text, ts, ps)
    xs = _dedupe_verbs(xs)

    tasks = []
    if not xs:
        conf = 0.5
        time, time_start, time_end = _time_fields(ts[0], now) if ts else (None, None, None)
        name, _ = _task_fields(text, ts, ps, xs)
        t = Task(
            task=name,
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
    multi = len(xs) > 1
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

        time, time_start, time_end = _time_fields(t, now)
        if multi:
            name, notes = x.action + x.object, ""
        else:
            name, notes = _task_fields(text, ts, ps, xs)
        task = Task(
            action=x.action,
            object=x.object,
            task=name,
            time_text=t.text if t else "",
            time=time,
            time_start=time_start,
            time_end=time_end,
            place=p.text if p else "",
            notes=notes,
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


def _time_fields(t, now=None):
    """从 TimeSpan 生成 (time, time_start, time_end) 三元组。
       明确范围（"3点到5点"）→ start + end
       截止标记（"周五之前/以内"）→ end=截止，start=当前
       普通时间（"周五""下午三点"）→ 视为开始时间
       无时间 → 全空
    """
    if t is None:
        return None, None, None
    if t.granularity == "range":
        date = t.date
        start = f"{date} {t.time_start}" if t.time_start else date
        end = f"{date} {t.time_end}" if t.time_end else date
        return start, start, end
    base = _fmt_time(t)
    if t.is_deadline:
        if now:
            start = now.strftime("%Y-%m-%d %H:%M")
        else:
            start = None
        return base, start, base
    return base, base, None


def _join_time(ts):
    """多个时间跨度时给出主时间（优先截止时间/完整日期）。"""
    if not ts:
        return None
    ts = sorted(ts, key=lambda s: (-int(s.is_deadline), -len(s.text)))
    return _fmt_time(ts[0])


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


def _build_llm_task(seg_text, lt):
    """从 LLM 返回的 dict 构造 Task。"""
    time = (lt["date"] and lt["time"] and f"{lt['date']} {lt['time']}"
            or lt["date"] or None)
    return Task(
        action=lt["action"], object=lt["object"],
        task=(lt["action"] + lt["object"]) if lt["action"] else seg_text,
        time_text=lt["time_text"],
        time=time, time_start=time, time_end=None,
        place=lt["place"], notes=lt.get("notes", ""), raw=seg_text,
        confidence=round(lt["confidence"], 3),
        source="llm",
    )


def _parse_all(text: str, ref: date, use_llm: bool,
               default_time=None, default_time_text="", now: datetime = None):
    client = OllamaClient() if use_llm else None
    if client is not None and not client._check():
        client = None

    structured = is_structured(text)
    all_tasks = []
    last_date = None
    last_time = None
    last_time_text = ""
    last_time_start = None

    for seg_text, off in segment(text):
        tasks, ts, ps, xs = _rule_tasks(seg_text, ref, now=now, context_date=last_date)

        if structured and len(tasks) > 1:
            tasks = _merge_item_tasks(tasks)

        # 头部默认时间
        if default_time:
            for t in tasks:
                if not t.time:
                    t.time = default_time
                    if not t.time_text:
                        t.time_text = default_time_text

        # LLM 兜底：无动作，或置信度 < 0.7 时调用
        has_action = any(x.action for x in xs)
        rule_conf = max((t.confidence for t in tasks), default=0)
        need_llm = (not has_action or rule_conf < 0.7) and client is not None and len(seg_text) >= 6
        if not need_llm:
            seg_out = tasks
        else:
            llm_tasks = client.parse_tasks(seg_text, ref)
            llm_tasks = [it for it in llm_tasks
                         if it["action"] or it["time_text"] or it["place"]]
            if llm_tasks:
                seg_out = [_build_llm_task(seg_text, lt) for lt in llm_tasks]
            else:
                seg_out = tasks

        # 顺便/并列继承
        if last_time and not structured:
            for t in seg_out:
                if not t.time and not t.time_text:
                    t.time = last_time
                    t.time_text = last_time_text
                    t.time_start = last_time_start

        all_tasks.extend(seg_out)

        # 更新上下文
        for t in seg_out:
            if t.time:
                d = t.time.split(" ")[0]
                try:
                    last_date = datetime.strptime(d, "%Y-%m-%d").date()
                except ValueError:
                    pass
                last_time = t.time
                last_time_text = t.time_text or ""
                last_time_start = t.time_start
                break

    return all_tasks


class TaskReader:
    def __init__(self, ref=None):
        explicit = ref is not None
        self.ref = _pick_ref(ref)
        if explicit:
            self.now = datetime.combine(self.ref, time(0, 0))
        else:
            self.now = datetime.now()

    def parse(self, sentence: str, use_llm: bool = True):
        """解析一句话，返回 Task 列表。"""
        if not sentence or not sentence.strip():
            return []
        text = normalize(sentence.strip())
        rest, header, is_title = extract_header(text)
        default_time, default_time_text = None, ""
        if header:
            ts = TimeParser(self.ref, now=self.now).parse(header)
            if ts:
                default_time = _join_time(ts)
                default_time_text = " ".join(s.text for s in ts)
        tasks = _parse_all(rest, self.ref, use_llm,
                           default_time=default_time,
                           default_time_text=default_time_text,
                           now=self.now)
        return tasks

    def parse_json(self, sentence: str, use_llm: bool = True):
        return [t.to_dict() for t in self.parse(sentence, use_llm=use_llm)]
