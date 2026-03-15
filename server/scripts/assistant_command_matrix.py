from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable, List

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_v2.main import _rate_buckets, app
from database.db import init_db


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
        json={"display_name": f"matrix_{tag}_{uuid.uuid4().hex[:6]}", "password": "123456"},
    )
    response.raise_for_status()
    token = response.json()["session_token"]
    return {"X-Session-Token": token}


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


def _assistant_messages(body: dict) -> list[str]:
    return [message["content"] for message in body.get("messages", []) if message.get("role") == "assistant"]


def make_cases() -> List[Case]:
    cases: List[Case] = []

    natural_zh = [
        ("zh-add-eat", "我要吃饭", "吃饭"),
        ("zh-add-sleep", "我得睡觉", "睡觉"),
        ("zh-add-walkdog", "我需要遛狗", "遛狗"),
        ("zh-add-daily-cook", "我每天都要做饭", "做饭"),
    ]
    for name, message, expected_title in natural_zh:
        def _case(message=message, expected_title=expected_title):
            headers = login(name)
            chat(headers, message)
            assert any(task["title"] == expected_title for task in active_tasks(headers))
        cases.append(Case(name, _case))

    natural_en = [
        ("en-add-lunch", "I need to eat lunch", "eat lunch"),
        ("en-add-run", "I want to run", "run"),
        ("en-add-sleep", "I have to sleep", "sleep"),
        ("en-add-daily-cook", "I cook every day", "cook"),
    ]
    for name, message, expected_title in natural_en:
        def _case(message=message, expected_title=expected_title):
            headers = login(name)
            chat(headers, message, "en")
            assert any(task["title"] == expected_title for task in active_tasks(headers))
        cases.append(Case(name, _case))

    recurrence_cases = [
        ("zh-weekly-plain-wed", "我周三有个会", "weekly", 2),
        ("zh-weekly-explicit-fri", "每周五我要去peter家", "weekly", 4),
        ("zh-relative-fri", "这周五我要去peter家", "temporary", None),
        ("zh-relative-sun", "这周日有个pre", "temporary", None),
        ("en-weekly-on", "i have plan on every monday to play game with my friends", "weekly", 0),
        ("en-weekly-no-on", "i have a plan every monday to drink water 2L", "weekly", 0),
    ]
    for name, message, expected_kind, expected_weekday in recurrence_cases:
        def _case(message=message, expected_kind=expected_kind, expected_weekday=expected_weekday):
            headers = login(name)
            chat(headers, message, "en" if message.lower().startswith("i ") else "zh")
            tasks = active_tasks(headers)
            assert tasks, tasks
            task = tasks[0]
            assert task["task_kind"] == expected_kind, task
            assert task.get("recurrence_weekday") == expected_weekday, task
        cases.append(Case(name, _case))

    def _multi_weekday():
        headers = login("multi-weekday")
        chat(headers, "i have plan on every monday and thursday to play game with my friends", "en")
        tasks = [task for task in active_tasks(headers) if "play game" in task["title"].lower()]
        weekdays = sorted(task["recurrence_weekday"] for task in tasks)
        assert weekdays == [0, 3], tasks
    cases.append(Case("en-multi-weekday", _multi_weekday))

    defer_cases = [
        ("zh-defer-tomorrow", "帮我把吃饭推迟到明天", "吃饭"),
        ("zh-defer-day-after", "帮我把吃午饭的任务推迟到后天", "eat lunch"),
        ("zh-defer-big-day-after", "把遛狗推迟到大后天", "walk dog"),
        ("zh-defer-next-weekday", "把 running 推迟到下周一", "running"),
        ("zh-defer-next-month", "把 leetcode 推迟到下个月", "leetcode"),
        ("en-defer-tomorrow", "Postpone eat lunch to tomorrow", "eat lunch"),
        ("en-defer-next-month", "Postpone finish capstone demo to next month", "finish capstone demo"),
    ]
    for name, message, expected_title in defer_cases:
        def _case(message=message, expected_title=expected_title):
            headers = login(name)
            lang = "en" if message.lower().startswith("postpone") else "zh"
            setup_message = "I need to " + expected_title if lang == "en" else f"我要{expected_title}"
            if expected_title in {"running", "leetcode", "finish capstone demo"}:
                client.post("/api/tasks", json={"title": expected_title, "task_kind": "temporary"}, headers=headers)
            else:
                chat(headers, setup_message, lang)
            chat(headers, message, lang)
            task = next(task for task in active_tasks(headers) if task["title"] == expected_title)
            assert task["due_date"], task
        cases.append(Case(name, _case))

    mark_cases = [
        ("zh-mark-daily", "把吃饭标成每日任务", "daily"),
        ("zh-mark-temp", "把吃饭标成临时任务", "temporary"),
        ("en-mark-daily", "Mark eat lunch as daily", "daily"),
        ("en-mark-temp", "Mark eat lunch as temporary", "temporary"),
    ]
    for name, message, expected_kind in mark_cases:
        def _case(message=message, expected_kind=expected_kind):
            headers = login(name)
            if "eat lunch" in message.lower():
                chat(headers, "I need to eat lunch", "en")
                lang = "en"
            else:
                chat(headers, "我要吃饭")
                lang = "zh"
            chat(headers, message, lang)
            title = "eat lunch" if lang == "en" else "吃饭"
            task = next(task for task in active_tasks(headers) if task["title"] == title)
            assert task["task_kind"] == expected_kind, task
        cases.append(Case(name, _case))

    def _list_tasks_case():
        headers = login("list-tasks")
        chat(headers, "我要吃饭")
        body = chat(headers, "我现在有哪些任务")
        messages = _assistant_messages(body)
        assert any("吃饭" in message for message in messages), messages
        assert not any("[p" in message for message in messages), messages
    cases.append(Case("list-tasks", _list_tasks_case))

    def _analysis_case():
        headers = login("analysis")
        body = chat(headers, "分析一下我最近的专注和完成情况")
        messages = _assistant_messages(body)
        assert any("专注" in message or "focus" in message.lower() for message in messages), messages
    cases.append(Case("analysis", _analysis_case))

    def _missing_task_followup():
        headers = login("missing-followup")
        body = chat(headers, "帮我删除不存在的任务")
        messages = _assistant_messages(body)
        assert any("更具体" in message or "没定位到" in message for message in messages), messages
        assert not any("已经处理" in message for message in messages), messages
    cases.append(Case("missing-task-followup", _missing_task_followup))

    def _compound_delete_add():
        headers = login("compound-zh")
        chat(headers, "我要吃饭")
        chat(headers, "删掉吃饭再加准备面试")
        tasks = active_tasks(headers)
        assert not any(task["title"] == "吃饭" for task in tasks), tasks
        assert any(task["title"] == "准备面试" for task in tasks), tasks
    cases.append(Case("compound-delete-add-zh", _compound_delete_add))

    def _duplicate_protection():
        headers = login("duplicate")
        chat(headers, "我要吃饭")
        chat(headers, "我要吃饭")
        tasks = active_tasks(headers)
        assert sum(1 for task in tasks if task["title"] == "吃饭") == 1, tasks
    cases.append(Case("duplicate-protection", _duplicate_protection))

    # Expand to many natural variants.
    zh_weekly_variants = [
        ("周一有个会议", 0),
        ("周二有个会议", 1),
        ("周三有个会议", 2),
        ("周四有个会议", 3),
        ("周五有个会议", 4),
        ("周六有个会议", 5),
        ("周日有个会议", 6),
        ("每周一有个会议", 0),
        ("每周二有个会议", 1),
        ("每周三有个会议", 2),
        ("每周四有个会议", 3),
        ("每周五有个会议", 4),
        ("每周六有个会议", 5),
        ("每周日有个会议", 6),
    ]
    for idx, (message, weekday) in enumerate(zh_weekly_variants, 1):
        def _case(message=message, weekday=weekday):
            headers = login(f"zh-weekly-{idx}")
            chat(headers, message)
            task = next(task for task in active_tasks(headers) if "会议" in task["title"] or task["title"] == "会")
            assert task["task_kind"] == "weekly", task
            assert task["recurrence_weekday"] == weekday, task
        cases.append(Case(f"zh-weekly-variant-{idx}", _case))

    en_every_variants = [
        ("I have a plan every monday to call mom", 0),
        ("I have a plan every tuesday to call mom", 1),
        ("I have a plan every wednesday to call mom", 2),
        ("I have a plan every thursday to call mom", 3),
        ("I have a plan every friday to call mom", 4),
        ("I have a plan every saturday to call mom", 5),
        ("I have a plan every sunday to call mom", 6),
    ]
    for idx, (message, weekday) in enumerate(en_every_variants, 1):
        def _case(message=message, weekday=weekday):
            headers = login(f"en-weekly-{idx}")
            chat(headers, message, "en")
            task = next(task for task in active_tasks(headers) if "call mom" in task["title"].lower())
            assert task["task_kind"] == "weekly", task
            assert task["recurrence_weekday"] == weekday, task
        cases.append(Case(f"en-weekly-variant-{idx}", _case))

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
    print(f"assistant_command_matrix: {len(cases) - len(failures)}/{len(cases)} passed")
    if failures:
        print("failures:")
        for name, detail in failures:
            print(f"- {name}: {detail}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
