"""Helpers for distinguishing recurring tasks from one-off tasks."""

from __future__ import annotations

from typing import Optional, Tuple
import re

from core.time import next_weekday_iso, upcoming_weekday_iso

VALID_TASK_KINDS = {"daily", "weekly", "temporary"}

WEEKDAY_PATTERNS = [
    (0, [r"每周一", r"星期一", r"周一", r"礼拜一", r"\bmondays?\b", r"\bmons?\b"]),
    (1, [r"每周二", r"星期二", r"周二", r"礼拜二", r"\btuesdays?\b", r"\btuesday\b", r"\btues?\b"]),
    (2, [r"每周三", r"星期三", r"周三", r"礼拜三", r"\bwednesdays?\b", r"\bweds?\b"]),
    (3, [r"每周四", r"星期四", r"周四", r"礼拜四", r"\bthursdays?\b", r"\bthursday\b", r"\bthu\b", r"\bthur\b", r"\bthurs\b"]),
    (4, [r"每周五", r"星期五", r"周五", r"礼拜五", r"\bfridays?\b", r"\bfris?\b"]),
    (5, [r"每周六", r"星期六", r"周六", r"礼拜六", r"\bsaturdays?\b", r"\bsats?\b"]),
    (6, [r"每周日", r"每周天", r"星期日", r"星期天", r"周日", r"周天", r"礼拜日", r"礼拜天", r"\bsundays?\b", r"\bsuns?\b"]),
]

WEEKLY_RECURRENCE_KEYWORDS = [
    "weekly",
    "every week",
    "each week",
    "每周",
    "每星期",
]

EN_RELATIVE_WEEKDAY_PATTERNS = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

ZH_RELATIVE_WEEKDAY_PATTERNS = {
    "一": 0,
    "1": 0,
    "二": 1,
    "2": 1,
    "三": 2,
    "3": 2,
    "四": 3,
    "4": 3,
    "五": 4,
    "5": 4,
    "六": 5,
    "6": 5,
    "日": 6,
    "天": 6,
    "7": 6,
    "0": 6,
}


def normalize_task_kind(value: Optional[str]) -> str:
    if value in VALID_TASK_KINDS:
        return value
    return "temporary"


def normalize_recurrence_weekday(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    try:
        weekday = int(value)
    except (TypeError, ValueError):
        return None
    return weekday if 0 <= weekday <= 6 else None


def strip_task_kind_markers(title: str) -> Tuple[str, Optional[str]]:
    text = (title or "").strip()
    lowered = text.lower()

    marker_map = [
        ("#daily", "daily"),
        ("[daily]", "daily"),
        ("#weekly", "weekly"),
        ("[weekly]", "weekly"),
        ("#temp", "temporary"),
        ("#temporary", "temporary"),
        ("[temp]", "temporary"),
    ]
    for marker, task_kind in marker_map:
        if marker in lowered:
            start = lowered.index(marker)
            original = text[start:start + len(marker)]
            cleaned = (text.replace(original, " ", 1)).strip()
            return cleaned, task_kind
    return text, None


def infer_recurrence_weekday(
    title: str,
    description: str = "",
    explicit_weekday: Optional[int] = None,
) -> Optional[int]:
    normalized = normalize_recurrence_weekday(explicit_weekday)
    if normalized is not None:
        return normalized

    combined = f"{title} {description}".strip().lower()
    for weekday, patterns in WEEKDAY_PATTERNS:
        if any(re.search(pattern, combined, flags=re.IGNORECASE) for pattern in patterns):
            return weekday
    return None


def has_explicit_weekly_recurrence(text: str, description: str = "") -> bool:
    combined = f"{text} {description}".strip().lower()
    if not combined:
        return False
    return any(keyword in combined for keyword in WEEKLY_RECURRENCE_KEYWORDS)


def infer_relative_due_date(title: str, description: str = "") -> Optional[str]:
    combined = f"{title} {description}".strip()
    normalized = combined.lower()
    if not normalized:
        return None

    for token, weekday in EN_RELATIVE_WEEKDAY_PATTERNS.items():
        if re.search(rf"\bthis {re.escape(token)}\b", normalized):
            return upcoming_weekday_iso(weekday)
        if re.search(rf"\bnext {re.escape(token)}\b", normalized):
            return next_weekday_iso(weekday)

    zh_match = re.search(r"(这|本|下)(?:周|星期)([一二三四五六日天12345670])", combined)
    if zh_match:
        weekday = ZH_RELATIVE_WEEKDAY_PATTERNS.get(zh_match.group(2))
        if weekday is None:
            return None
        return upcoming_weekday_iso(weekday) if zh_match.group(1) in {"这", "本"} else next_weekday_iso(weekday)

    return None


def infer_task_kind(
    title: str,
    description: str = "",
    due_date: Optional[str] = None,
    explicit: Optional[str] = None,
) -> str:
    normalized = normalize_task_kind(explicit)
    if explicit in VALID_TASK_KINDS:
        return normalized

    combined = f"{title} {description}".strip().lower()
    weekly_weekday = infer_recurrence_weekday(title, description)
    daily_keywords = [
        "daily",
        "every day",
        "routine",
        "recurring",
        "habit",
        "每 天",
        "每天",
        "每日",
        "日常",
        "例行",
    ]
    weekly_keywords = [*WEEKLY_RECURRENCE_KEYWORDS, "周会"]
    temporary_keywords = [
        "temporary",
        "one-off",
        "one off",
        "temp",
        "临时",
        "一次性",
        "这次",
    ]

    if any(keyword in combined for keyword in daily_keywords):
        return "daily"
    if due_date:
        return "temporary"
    if infer_relative_due_date(title, description):
        return "temporary"
    if weekly_weekday is not None:
        return "weekly"
    if any(keyword in combined for keyword in weekly_keywords):
        return "weekly"
    if any(keyword in combined for keyword in temporary_keywords):
        return "temporary"
    return "temporary"
