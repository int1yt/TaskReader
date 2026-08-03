"""任务数据结构定义。"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Span:
    """原始文本中的一个匹配片段（时间/地点/动作等）。"""
    text: str
    start: int = 0
    end: int = 0
    confidence: float = 1.0


@dataclass
class TimeSpan(Span):
    """时间匹配片段。"""
    date: Optional[str] = None      # 归一化日期 YYYY-MM-DD
    time: Optional[str] = None      # 归一化时间 HH:MM（可选）
    granularity: str = "date"       # date / datetime / time / range
    is_deadline: bool = False       # 是否截止时间
    is_clock: bool = False          # 是否有明确时刻（"三点"），用于点时间是否视为开始时间
    original: str = ""              # 原始时间短语（含限定词）
    time_start: Optional[str] = None  # 归一化起始时刻 HH:MM（时间范围时）
    time_end: Optional[str] = None    # 归一化结束时刻 HH:MM（时间范围时）


@dataclass
class PlaceSpan(Span):
    """地点匹配片段。"""


@dataclass
class ActionSpan(Span):
    """动作匹配片段。"""
    action: str = ""
    object: str = ""
    canonical: str = ""


@dataclass
class Task:
    """一个任务/计划。"""
    action: str = ""
    object: str = ""
    task: str = ""                      # 任务名（动作+对象或原始描述）
    time_text: str = ""
    time: Optional[str] = None          # 归一化日期时间（主时间/范围起点）
    time_start: Optional[str] = None    # 归一化起始日期时间（时间范围时）
    time_end: Optional[str] = None      # 归一化结束日期时间（时间范围/截止时）
    place: str = ""
    notes: str = ""                     # 附加信息（列表项内其它内容等）
    raw: str = ""
    confidence: float = 0.0
    source: str = "rule"                # rule / llm / hybrid
    span: object = field(default=None, repr=False)

    def to_dict(self) -> dict:
        d = {
            "task": self.task or (self.action + self.object if self.action else self.raw),
            "action": self.action,
            "object": self.object,
            "time_start": self.time_start,
            "time_end": self.time_end,
            "time": self.time,
            "time_text": self.time_text,
            "place": self.place,
            "notes": self.notes,
            "raw": self.raw,
            "confidence": round(self.confidence, 3),
            "source": self.source,
        }
        return d
