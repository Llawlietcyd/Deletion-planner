from __future__ import annotations

from datetime import date, datetime, timedelta
import calendar
import re
from zoneinfo import ZoneInfo

APP_TIMEZONE = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def local_now() -> datetime:
    return datetime.now(APP_TIMEZONE)


def local_today() -> date:
    return local_now().date()


def local_today_iso() -> str:
    return local_today().isoformat()


def local_date_offset(days: int = 0) -> date:
    return local_today() + timedelta(days=days)


def local_date_offset_iso(days: int = 0) -> str:
    return local_date_offset(days).isoformat()


def next_week_iso() -> str:
    return local_date_offset_iso(7)


def next_weekday_iso(weekday: int) -> str:
    today = local_today()
    start_of_next_week = today + timedelta(days=(7 - today.weekday()))
    target = start_of_next_week + timedelta(days=weekday)
    return target.isoformat()


def upcoming_weekday_iso(weekday: int) -> str:
    today = local_today()
    delta = (weekday - today.weekday()) % 7
    target = today + timedelta(days=delta)
    return target.isoformat()


def upcoming_weekend_iso() -> str:
    today = local_today()
    days_until_saturday = (5 - today.weekday()) % 7
    target = today + timedelta(days=days_until_saturday)
    return target.isoformat()


def next_month_iso() -> str:
    today = local_today()
    if today.month == 12:
        year = today.year + 1
        month = 1
    else:
        year = today.year
        month = today.month + 1
    last_day = calendar.monthrange(year, month)[1]
    target = date(year, month, min(today.day, last_day))
    return target.isoformat()


def normalize_date_string(value: str | None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw

    match = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})", raw)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        today = local_today()
        try:
            return date(today.year, month, day).isoformat()
        except ValueError:
            return raw

    match = re.fullmatch(r"(\d{4})[./](\d{1,2})[./](\d{1,2})", raw)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return raw

    return raw


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def datetime_to_iso(value: datetime | None) -> str | None:
    aware = ensure_utc(value)
    return aware.isoformat() if aware else None
