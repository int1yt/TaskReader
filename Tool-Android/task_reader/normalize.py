"""文本预处理：全角转半角、统一标点、简繁转换（可选）。"""
from __future__ import annotations


def _full_to_half(text: str) -> str:
    out = []
    for ch in text:
        code = ord(ch)
        if code == 0x3000:                      # 全角空格
            out.append(" ")
        elif 0xFF01 <= code <= 0xFF5E:          # 全角 ASCII
            out.append(chr(code - 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)


_PUNCT_MAP = {
    "，": ",", "；": ";", "！": "!", "？": "?",
    "、": ",", "（": "(", "）": ")", "【": "[", "】": "]",
    "《": "<", "》": ">", "“": '"', "”": '"', "‘": "'", "’": "'",
}

# 紧凑时间词 → 展开为"相对日 + 时段"，便于时间解析
_TIME_COMPACT = {
    "明早": "明天早上", "明晚": "明天晚上", "明中午": "明天中午",
    "今早": "今天早上", "今晚": "今天晚上", "今夜": "今天晚上", "今中午": "今天中午",
    "昨晚": "昨天晚上", "昨夜": "昨天晚上", "前晚": "前天晚上",
    "大后天早上": "大后天早上", "大前天晚上": "大前天晚上",
}


def _unify_punct(text: str) -> str:
    return "".join(_PUNCT_MAP.get(ch, ch) for ch in text)


def _expand_compact(text: str) -> str:
    for k in sorted(_TIME_COMPACT, key=len, reverse=True):
        if k in text:
            text = text.replace(k, _TIME_COMPACT[k])
    return text


def _load_t2s():
    """尝试加载 opencc 做简繁转换；未安装则返回 None。"""
    try:
        from opencc import OpenCC  # type: ignore
        return OpenCC("t2s")
    except Exception:
        return None


_T2S = _load_t2s()


def normalize(text: str) -> str:
    """规范化输入。返回处理后的文本（与原文同字符序，便于回退）。"""
    if not text:
        return text
    text = _full_to_half(text)
    text = _unify_punct(text)
    text = _expand_compact(text)
    if _T2S is not None:
        text = _T2S.convert(text)
    return text
