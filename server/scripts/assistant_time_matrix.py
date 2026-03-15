from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import uuid
from typing import Callable, List

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_v2.main import _rate_buckets, app
from database.db import init_db
from core.time import (
    local_date_offset_iso,
    next_month_iso,
    next_week_iso,
    next_weekday_iso,
    normalize_date_string,
    upcoming_weekday_iso,
    upcoming_weekend_iso,
)


init_db()
client = TestClient(app)


@dataclass
class Case:
    name: str
    fn: Callable[[], None]


def login(tag: str) -> dict[str, str]:
    _rate_buckets.clear()
    response = client.post(
        "/api/session/login",
        json={"display_name": f"time_{tag}_{uuid.uuid4().hex[:6]}", "password": "123456"},
    )
    response.raise_for_status()
    return {"X-Session-Token": response.json()["session_token"]}


def chat(headers: dict[str, str], message: str, lang: str = "zh") -> dict:
    _rate_buckets.clear()
    response = client.post("/api/assistant/chat", json={"message": message, "lang": lang}, headers=headers)
    response.raise_for_status()
    return response.json()


def active_tasks(headers: dict[str, str]) -> list[dict]:
    _rate_buckets.clear()
    response = client.get("/api/tasks?status=active", headers=headers)
    response.raise_for_status()
    return response.json()


def _first_task(headers: dict[str, str]) -> dict:
    tasks = active_tasks(headers)
    assert tasks, tasks
    return tasks[0]


def make_cases() -> List[Case]:
    cases: List[Case] = []

    zh_add_cases = [
        ("zh-add-tomorrow", "我要明天交论文", "交论文", local_date_offset_iso(1)),
        ("zh-add-day-after", "我要后天面试", "面试", local_date_offset_iso(2)),
        ("zh-add-three-days", "我要大后天去银行", "去银行", local_date_offset_iso(3)),
        ("zh-add-next-week", "我要下周做预算", "做预算", next_week_iso()),
        ("zh-add-next-weekday", "我要下周一开会", "开会", next_weekday_iso(0)),
        ("zh-add-next-month", "我要下个月交房租", "交房租", next_month_iso()),
        ("zh-add-weekend", "我要周末买菜", "买菜", upcoming_weekend_iso()),
        ("zh-add-explicit-short", "我要3.17交作业", "交作业", normalize_date_string("3.17")),
        ("zh-add-explicit-slash", "我要03/17交作业", "交作业", normalize_date_string("03/17")),
        ("zh-add-explicit-full", "我要2026/03/17交作业", "交作业", "2026-03-17"),
    ]
    for name, message, title, due in zh_add_cases:
        def _case(message=message, title=title, due=due):
            headers = login(name)
            chat(headers, message)
            task = next(task for task in active_tasks(headers) if task["title"] == title)
            assert task["due_date"] == due, task
        cases.append(Case(name, _case))

    en_add_cases = [
        ("en-add-tomorrow", "I need to submit report tomorrow", "submit report", local_date_offset_iso(1)),
        ("en-add-tonight", "I need to buy groceries tonight", "buy groceries", local_date_offset_iso(0)),
        ("en-add-next-monday", "I need to call mom next monday", "call mom", next_weekday_iso(0)),
        ("en-add-this-friday", "I need to submit report this friday", "submit report", upcoming_weekday_iso(4)),
        ("en-add-on-friday", "I need to submit report on friday", "submit report", upcoming_weekday_iso(4)),
        ("en-add-next-month", "I need to pay rent next month", "pay rent", next_month_iso()),
        ("en-add-date-short", "I need to submit report 3/17", "submit report", normalize_date_string("3/17")),
        ("en-add-date-full", "I need to submit report 2026/03/17", "submit report", "2026-03-17"),
    ]
    for name, message, title, due in en_add_cases:
        def _case(message=message, title=title, due=due):
            headers = login(name)
            chat(headers, message, "en")
            task = next(task for task in active_tasks(headers) if task["title"] == title)
            assert task["due_date"] == due, task
        cases.append(Case(name, _case))

    defer_cases = [
        ("zh-defer-tonight", "把买菜推迟到今晚", "买菜", local_date_offset_iso(0), "zh"),
        ("zh-defer-next-week", "把买菜推迟到下周", "买菜", next_week_iso(), "zh"),
        ("zh-defer-next-weekday", "把买菜推迟到下周五", "买菜", next_weekday_iso(4), "zh"),
        ("zh-defer-next-month", "把买菜推迟到下个月", "买菜", next_month_iso(), "zh"),
        ("en-defer-tonight", "Postpone buy groceries to tonight", "buy groceries", local_date_offset_iso(0), "en"),
        ("en-defer-next-week", "Postpone buy groceries to next week", "buy groceries", next_week_iso(), "en"),
        ("en-defer-next-weekday", "Postpone buy groceries to next friday", "buy groceries", next_weekday_iso(4), "en"),
        ("en-defer-next-month", "Postpone buy groceries to next month", "buy groceries", next_month_iso(), "en"),
    ]
    for name, message, title, due, lang in defer_cases:
        def _case(message=message, title=title, due=due, lang=lang):
            headers = login(name)
            client.post("/api/tasks", json={"title": title, "task_kind": "temporary"}, headers=headers)
            chat(headers, message, lang)
            task = next(task for task in active_tasks(headers) if task["title"] == title)
            assert task["due_date"] == due, task
        cases.append(Case(name, _case))

    return cases


def main() -> None:
    cases = make_cases()
    failures: list[tuple[str, str]] = []
    for case in cases:
        try:
            case.fn()
            print(f"PASS {case.name}")
        except Exception as exc:  # noqa: BLE001
            failures.append((case.name, repr(exc)))
            print(f"FAIL {case.name}: {exc}")
    print()
    print(f"assistant_time_matrix: {len(cases) - len(failures)}/{len(cases)} passed")
    if failures:
        print("failures:")
        for name, detail in failures:
            print(f"- {name}: {detail}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
