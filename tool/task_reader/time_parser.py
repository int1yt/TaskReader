"""中文时间抽取与归一化。

把"下周三""明早八点""两周后""8月5日"等解析为绝对日期/时间，
以参考时间（默认今天）为基准换算相对时间。
"""
from __future__ import annotations

import calendar
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from .task_model import TimeSpan

_DICT_DIR = Path(__file__).parent / "dicts"
with open(_DICT_DIR / "time.json", encoding="utf-8") as f:
    _TIME_DICT = json.load(f)

_DAYPARTS = _TIME_DICT["时段词"]
_REL_DAYS = _TIME_DICT["相对日"]
_WEEKDAYS = _TIME_DICT["星期"]
_REL_PERIODS = _TIME_DICT["相对周期"]
_MONTH_BOUND = _TIME_DICT["时段边界"]

# ---------------- 中文数字转换 ----------------

_CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000, "亿": 100000000}


def cn2int(s: str) -> int:
    """中文数字转整数：十三→13，两→2，一百零五→105。"""
    total = section = num = 0
    for ch in s:
        if ch in _CN_DIGITS:
            num = _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            u = _CN_UNITS[ch]
            if u >= 10000:
                section = (section + num) if num else section
                total += section * u
                section = num = 0
            else:
                section += (num if num else 1) * u
                num = 0
    section += num
    return total + section


def _cn_num_run(text: str, i: int) -> str:
    """从 i 起连续取中文数字字符。"""
    j = i
    while j < len(text):
        if text[j] in _CN_DIGITS or text[j] in "十百千万亿":
            j += 1
        else:
            break
    return text[i:j]


# ---------------- 日期辅助 ----------------

def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    last = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, last))


def _month_end(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def _weekday_in_week(ref: date, wd: int, week_offset: int = 0) -> date:
    monday = ref - timedelta(days=ref.weekday())
    return monday + timedelta(days=wd + 7 * week_offset)


# ---------------- 正则 ----------------

_CN_DIGIT_CHARS = "".join(_CN_DIGITS)
_CN_HOUR = rf"[0-9]{{1,2}}|[{_CN_DIGIT_CHARS}十百]+"
_CN_NUM = rf"[0-9]+|[{_CN_DIGIT_CHARS}十百千]+"

_PATTERNS = [
    ("abs_ymd_cn", re.compile(r"(?P<y>\d{4})年(?P<mo>\d{1,2})月(?P<d>\d{1,2})[日号]?")),
    ("abs_md_cn", re.compile(r"(?P<mo>\d{1,2})月(?P<d>\d{1,2})[日号]?")),
    ("abs_ymd_num", re.compile(r"(?P<y>\d{4})[-/.](?P<mo>\d{1,2})[-/.](?P<d>\d{1,2})")),
    ("abs_md_num", re.compile(r"(?<!\d)(?P<mo>\d{1,2})[-/.](?P<d>\d{1,2})(?!\d)")),
    ("rel_day", re.compile("|".join(sorted(_REL_DAYS, key=len, reverse=True)))),
    ("weekday", re.compile(r"(?P<pre>[上本这大下]?个?)(?:周|星期|礼拜)(?P<wd>[一二三四五六日天])")),
    ("period_week", re.compile(r"(?P<pre>[本这上])(?:个)?(?:周|星期)(?![一二三四五六日天])")),
    ("period_week_next", re.compile(r"下(?:个)?(?:周|星期)(?![一二三四五六日天])")),
    ("period_month", re.compile(r"(?P<pre>这个|本月|上月|上个月|下月|下个月|当月)")),
    ("period_year", re.compile(r"(?P<pre>今年|去年|明年)")),
    ("weekend", re.compile(r"(?P<pre>[上下本这]?)(?:周)?末")),
    ("month_bound", re.compile(r"(?P<pre>[本这上]?下?个月?)?(?P<b>月初|月中|月底|月末)")),
    ("x_after", re.compile(rf"(?P<num>{_CN_NUM})个?(?P<unit>天|周|个月|年)(?P<suf>后|内|之内|以前|之前|前|以后)")),
]

_DEADLINE_MARKERS = ["之前", "以前", "截止", "截止到", "截至", "以内", "之内"]

_DAYPART_ALT = "|".join(sorted(_DAYPARTS, key=len, reverse=True))
_TIME_CN = re.compile(
    rf"(?P<dp>{_DAYPART_ALT})?(?:的)?(?P<h>{_CN_HOUR})[点时]"
    rf"(?:(?P<half>半)|(?P<mi>\d{{1,2}})分?)?"
)
_TIME_COLON = re.compile(r"(?<!\d)(?P<h>\d{1,2})[:：](?P<mi>\d{2})(?!\d)")
_TIME_DAYPART = re.compile(rf"(?P<dp>{_DAYPART_ALT})(?![点时])")
# 时间范围：下午3点到5点 / 3点至5点半 / 2:00到4:00
_TIME_RANGE = re.compile(
    rf"(?P<dp>{_DAYPART_ALT})?(?P<h1>{_CN_HOUR})[点时](?:(?P<mi1>\d{{1,2}})分?)?"
    rf"(?P<sep>到|至|~|~|—|--|->)"
    rf"(?P<h2>{_CN_HOUR})[点时](?:(?P<half>半)|(?P<mi2>\d{{1,2}})分?)?"
)
_TIME_RANGE_COLON = re.compile(
    rf"(?P<h1>\d{{1,2}})[:：](?P<mi1>\d{{2}})(?P<sep>到|至|~|~|—|--|->)(?P<h2>\d{{1,2}})[:：](?P<mi2>\d{{2}})"
)


# ---------------- 解析器 ----------------

class TimeParser:
    """时间解析器。ref 为参考日期（默认今天）。"""

    def __init__(self, ref=None):
        if ref is None:
            ref = date.today()
        if isinstance(ref, datetime):
            ref = ref.date()
        self.ref = ref

    def _resolve(self, name: str, m: re.Match):
        """返回 (date, granularity, confidence) 或 None。"""
        ref = self.ref
        if name == "abs_ymd_cn":
            return date(int(m.group("y")), int(m.group("mo")), int(m.group("d"))), "date", 0.98
        if name == "abs_ymd_num":
            return date(int(m.group("y")), int(m.group("mo")), int(m.group("d"))), "date", 0.98
        if name == "abs_md_cn":
            d = date(ref.year, int(m.group("mo")), int(m.group("d")))
            if d < ref - timedelta(days=30):
                d = d.replace(year=d.year + 1)
            return d, "date", 0.95
        if name == "abs_md_num":
            mo, dd = int(m.group("mo")), int(m.group("d"))
            if mo == 0 or dd == 0:
                return None
            d = date(ref.year, mo, dd)
            if d < ref - timedelta(days=30):
                d = d.replace(year=d.year + 1)
            return d, "date", 0.95
        if name == "rel_day":
            return ref + timedelta(days=_REL_DAYS[m.group(0)]), "date", 0.97
        if name == "weekday":
            pre = m.group("pre")
            wd = _WEEKDAYS[m.group("wd")]
            if pre in ("下", "下个"):
                d = _weekday_in_week(ref, wd, week_offset=1)
            elif pre in ("上", "上个"):
                d = _weekday_in_week(ref, wd, week_offset=-1)
            else:
                d = _weekday_in_week(ref, wd, week_offset=0)
                if d < ref and not pre:
                    d = _weekday_in_week(ref, wd, week_offset=1)
            return d, "date", 0.92
        if name == "period_week":
            pre = m.group("pre")
            off = 0 if pre in ("本", "这") else -1
            d = _weekday_in_week(ref, 0, week_offset=off)
            return d, "week", 0.6
        if name == "period_week_next":
            d = _weekday_in_week(ref, 0, week_offset=1)
            return d, "week", 0.6
        if name == "period_month":
            pre = m.group("pre")
            off = {"上个月": -1, "上月": -1, "下个月": 1, "下月": 1}.get(pre, 0)
            d = _add_months(ref.replace(day=1), off)
            return d, "month", 0.6
        if name == "period_year":
            off = {"去年": -1, "明年": 1}.get(m.group("pre"), 0)
            return date(ref.year + off, 1, 1), "year", 0.6
        if name == "weekend":
            pre = m.group("pre")
            off = {"上": -1, "下": 1}.get(pre, 0)
            if pre == "下":
                sat = _weekday_in_week(ref, 5, week_offset=1)
            else:
                sat = _weekday_in_week(ref, 5, week_offset=off)
                if sat < ref:
                    sat = _weekday_in_week(ref, 5, week_offset=1)
            return sat, "date", 0.85
        if name == "month_bound":
            b = m.group("b")
            pre = m.group("pre") or ""
            off = 0
            if "下" in pre:
                off = 1
            elif "上" in pre:
                off = -1
            base = _add_months(ref, off)
            if b in ("月底", "月末"):
                d = _month_end(base)
            elif b == "月中":
                d = base.replace(day=15)
            else:
                d = base.replace(day=1)
            return d, "date", 0.8
        if name == "x_after":
            num = m.group("num")
            n = int(num) if num.isdigit() else cn2int(num)
            unit = m.group("unit")
            suf = m.group("suf")
            sign = -1 if suf == "前" else 1
            if unit == "天":
                d = ref + timedelta(days=sign * n)
            elif unit == "周":
                d = ref + timedelta(days=sign * 7 * n)
            elif unit == "个月":
                d = _add_months(ref, sign * n)
            else:
                d = _add_months(ref, sign * n * 12)
            is_deadline = suf in ("内", "之内", "以内")
            return d, "date", 0.85
        return None

    def _find_dates(self, text: str):
        hits = []
        for name, pat in _PATTERNS:
            for m in pat.finditer(text):
                r = self._resolve(name, m)
                if r is None:
                    continue
                d, gran, conf = r
                hits.append({
                    "name": name, "start": m.start(), "end": m.end(),
                    "date": d, "granularity": gran, "confidence": conf,
                    "is_deadline": False,
                })
        return _resolve_overlaps(hits)

    def _find_times(self, text: str):
        hits = []
        for pat in (_TIME_CN, _TIME_COLON, _TIME_DAYPART):
            for m in pat.finditer(text):
                dp = m.groupdict().get("dp")
                h = m.groupdict().get("h")
                if m.re is _TIME_DAYPART:
                    hour = _DAYPARTS[dp]
                    minute = 0
                    conf = 0.7
                elif h is None:
                    continue
                else:
                    hour = int(h) if h.isdigit() else cn2int(h)
                    if m.groupdict().get("half"):
                        minute = 30
                    elif m.groupdict().get("mi"):
                        minute = int(m.group("mi"))
                    else:
                        minute = 0
                    if m.re is _TIME_COLON:
                        if hour > 23 or minute > 59:
                            continue
                    else:
                        if hour > 24:
                            continue
                        hour = self._apply_daypart(dp, hour)
                    if hour == 24:
                        hour = 0
                    conf = 0.85 if dp else 0.8
                hits.append({
                    "start": m.start(), "end": m.end(),
                    "hour": hour, "minute": minute, "confidence": conf,
                    "is_deadline": False,
                })
        return _resolve_overlaps(hits)

    @staticmethod
    def _apply_daypart(dp, hour):
        if not dp:
            return hour
        if dp in ("凌晨", "午夜", "清晨"):
            return hour
        if dp in ("早晨", "早上", "上午", "中午"):
            return hour
        if dp == "下午":
            return hour + 12 if hour < 12 else hour
        if dp in ("傍晚", "晚上", "夜间", "深夜"):
            return hour + 12 if hour <= 12 else hour
        return hour

    def _find_ranges(self, text: str):
        """识别时间范围（3点到5点 / 2:00-4:00），返回类似 time_hits 的结构。"""
        hits = []
        for pat in (_TIME_RANGE_COLON, _TIME_RANGE):
            for m in pat.finditer(text):
                dp = m.groupdict().get("dp") or ""
                if m.re is _TIME_RANGE_COLON:
                    h1, mi1 = int(m.group("h1")), int(m.group("mi1"))
                    h2, mi2 = int(m.group("h2")), int(m.group("mi2"))
                    if h1 > 23 or h2 > 23 or mi1 > 59 or mi2 > 59:
                        continue
                    conf = 0.85
                else:
                    h1 = int(m.group("h1")) if m.group("h1").isdigit() else cn2int(m.group("h1"))
                    h2 = int(m.group("h2")) if m.group("h2").isdigit() else cn2int(m.group("h2"))
                    mi1 = int(m.group("mi1") or 0) if m.group("mi1") else 0
                    if m.group("half"):
                        mi2 = 30
                    elif m.group("mi2"):
                        mi2 = int(m.group("mi2"))
                    else:
                        mi2 = 0
                    if h1 > 24 or h2 > 24:
                        continue
                    h1 = self._apply_daypart(dp, h1)
                    h2 = self._apply_daypart(dp, h2)
                    conf = 0.8
                if h1 == 24:
                    h1 = 0
                if h2 == 24:
                    h2 = 0
                if h2 < h1:
                    h2 += 24
                hits.append({
                    "start": m.start(), "end": m.end(),
                    "hour_start": h1, "minute_start": mi1,
                    "hour_end": h2, "minute_end": mi2,
                    "confidence": conf, "is_deadline": False,
                })
        return _resolve_overlaps(hits)

    def parse(self, text: str):
        """解析子句中的所有时间，返回 TimeSpan 列表（按原文顺序）。"""
        if not text:
            return []
        date_hits = self._find_dates(text)
        range_hits = self._find_ranges(text)
        time_hits = [th for th in self._find_times(text)
                     if not any(th["start"] < rh["end"] and rh["start"] < th["end"]
                                for rh in range_hits)]

        for dh in date_hits:
            end = dh["end"]
            for marker in _DEADLINE_MARKERS:
                if text[end:end + len(marker)] == marker:
                    dh["is_deadline"] = True
                    break
        for th in time_hits:
            end = th["end"]
            for marker in _DEADLINE_MARKERS:
                if text[end:end + len(marker)] == marker:
                    th["is_deadline"] = True
                    break
        for rh in range_hits:
            end = rh["end"]
            for marker in _DEADLINE_MARKERS:
                if text[end:end + len(marker)] == marker:
                    rh["is_deadline"] = True
                    break

        spans = []
        used_dates = set()

        for rh in range_hits:
            attached = None
            for dh in date_hits:
                gap = rh["start"] - dh["end"]
                if 0 <= gap <= 8:
                    attached = dh
                    break
            if attached is not None and id(attached) not in used_dates:
                used_dates.add(id(attached))
                d = attached["date"]
            else:
                d = self.ref
            ts = TimeSpan(
                text=text[rh["start"]:rh["end"]],
                start=rh["start"], end=rh["end"],
                confidence=rh["confidence"],
                date=f"{d:%Y-%m-%d}",
                time=f"{rh['hour_start']:02d}:{rh['minute_start']:02d}",
                granularity="range",
                is_deadline=rh["is_deadline"],
                original=text[rh["start"]:rh["end"]],
                time_start=f"{rh['hour_start']:02d}:{rh['minute_start']:02d}",
                time_end=f"{rh['hour_end']:02d}:{rh['minute_end']:02d}",
            )
            spans.append(ts)

        for th in time_hits:
            attached = None
            for dh in date_hits:
                gap = th["start"] - dh["end"]
                if 0 <= gap <= 8:
                    attached = dh
                    break
            if attached is not None and id(attached) not in used_dates:
                used_dates.add(id(attached))
                d = attached["date"]
                conf = attached["confidence"] * 0.6 + th["confidence"] * 0.4
                ts = TimeSpan(
                    text=text[attached["start"]:th["end"]],
                    start=attached["start"], end=th["end"],
                    confidence=round(conf, 3),
                    date=f"{d:%Y-%m-%d}",
                    time=f"{th['hour']:02d}:{th['minute']:02d}",
                    granularity="datetime",
                    is_deadline=attached["is_deadline"] or th["is_deadline"],
                    original=text[attached["start"]:th["end"]],
                )
                spans.append(ts)
            else:
                d = self.ref
                ts = TimeSpan(
                    text=text[th["start"]:th["end"]],
                    start=th["start"], end=th["end"],
                    confidence=th["confidence"],
                    date=f"{d:%Y-%m-%d}",
                    time=f"{th['hour']:02d}:{th['minute']:02d}",
                    granularity="time",
                    is_deadline=th["is_deadline"],
                    original=text[th["start"]:th["end"]],
                )
                spans.append(ts)

        for dh in date_hits:
            if id(dh) in used_dates:
                continue
            ts = TimeSpan(
                text=text[dh["start"]:dh["end"]],
                start=dh["start"], end=dh["end"],
                confidence=dh["confidence"],
                date=f"{dh['date']:%Y-%m-%d}",
                time=None,
                granularity=dh["granularity"],
                is_deadline=dh["is_deadline"],
                original=text[dh["start"]:dh["end"]],
            )
            spans.append(ts)

        spans.sort(key=lambda s: (s.start, -(s.end - s.start)))
        return _drop_overlaps(spans)


def _resolve_overlaps(hits):
    """同一位置多个正则命中时保留更长/更精确的一条。"""
    hits = sorted(hits, key=lambda h: (h["start"], -(h["end"] - h["start"])))
    out = []
    for h in hits:
        if out and h["start"] < out[-1]["end"]:
            prev = out[-1]
            if (h["end"] - h["start"]) > (prev["end"] - prev["start"]):
                out[-1] = h
            continue
        out.append(h)
    return out


def _drop_overlaps(spans):
    out = []
    for s in spans:
        if out and s.start < out[-1].end:
            continue
        out.append(s)
    return out
