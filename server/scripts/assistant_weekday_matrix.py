"""High-volume weekday semantics regression matrix for the assistant.

This intentionally stress-tests the edge where recurring weekly phrases and
one-off relative weekday phrases can get mixed up.
"""

from __future__ import annotations

import os
import sys
from uuid import uuid4


SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SERVER_DIR)

os.environ["DATABASE_URL"] = "sqlite:///assistant_weekday_matrix.db"
os.environ["LLM_PROVIDER"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402

from api_v2.main import app, _rate_buckets  # noqa: E402
from database.db import init_db  # noqa: E402


init_db()
client = TestClient(app)


def login() -> None:
    _rate_buckets.clear()
    client.headers.pop("X-Session-Token", None)
    username = f"matrix-{uuid4().hex[:8]}"
    res = client.post("/api/session/login", json={"display_name": username, "password": "matrix-pass"})
    assert res.status_code == 200, res.text
    client.headers["X-Session-Token"] = res.json()["session_token"]


def active_tasks():
    res = client.get("/api/tasks?status=active")
    assert res.status_code == 200, res.text
    return res.json()


def assert_single_task(message: str, *, title: str, kind: str, recurrence_weekday=None, due_date_expected=False, lang="zh"):
    login()
    res = client.post("/api/assistant/chat", json={"message": message, "lang": lang})
    assert res.status_code == 200, (message, res.text)
    tasks = active_tasks()
    task = next((item for item in tasks if item["title"] == title), None)
    assert task is not None, (message, tasks)
    assert task["task_kind"] == kind, (message, task)
    assert task["recurrence_weekday"] == recurrence_weekday, (message, task)
    if due_date_expected:
      assert task["due_date"], (message, task)
    else:
      assert task["due_date"] is None, (message, task)


def assert_multi_weekly(message: str, *, title: str, weekdays: list[int]):
    login()
    res = client.post("/api/assistant/chat", json={"message": message, "lang": "en"})
    assert res.status_code == 200, (message, res.text)
    tasks = [item for item in active_tasks() if item["title"] == title]
    assert sorted(item["recurrence_weekday"] for item in tasks) == sorted(weekdays), (message, tasks)


def main() -> None:
    zh_days = [("一", 0), ("二", 1), ("三", 2), ("四", 3), ("五", 4), ("六", 5), ("日", 6)]
    en_days = [
        ("monday", 0),
        ("tuesday", 1),
        ("wednesday", 2),
        ("thursday", 3),
        ("friday", 4),
        ("saturday", 5),
        ("sunday", 6),
    ]

    cases_run = 0

    zh_weekly_prefixes = ["周", "星期", "礼拜", "每周", "每星期", "每礼拜"]
    for prefix in zh_weekly_prefixes:
        for day_char, weekday in zh_days:
            assert_single_task(
                f"{prefix}{day_char}有个会",
                title="会",
                kind="weekly",
                recurrence_weekday=weekday,
                due_date_expected=False,
            )
            cases_run += 1

    zh_relative_prefixes = ["这周", "本周", "下周", "这星期", "本星期", "下星期"]
    for prefix in zh_relative_prefixes:
        for day_char, _weekday in zh_days:
            assert_single_task(
                f"{prefix}{day_char}去上班",
                title="去上班",
                kind="temporary",
                recurrence_weekday=None,
                due_date_expected=True,
            )
            cases_run += 1

    for day_name, weekday in en_days:
        assert_single_task(
            f"i have plan on every {day_name} to call mom",
            title="call mom",
            kind="weekly",
            recurrence_weekday=weekday,
            due_date_expected=False,
            lang="en",
        )
        cases_run += 1

    for day_name, _weekday in en_days:
        assert_single_task(
            f"I need to call mom next {day_name}",
            title="call mom",
            kind="temporary",
            recurrence_weekday=None,
            due_date_expected=True,
            lang="en",
        )
        cases_run += 1

    assert_multi_weekly(
        "i have plan on every monday and thursday to play game with my friends",
        title="play game with my friends",
        weekdays=[0, 3],
    )
    cases_run += 1

    assert_multi_weekly(
        "i have plan on every tuesday and friday to go to gym",
        title="go to gym",
        weekdays=[1, 4],
    )
    cases_run += 1

    assert cases_run == 100, cases_run
    print(f"assistant_weekday_matrix: {cases_run}/100 passed")


if __name__ == "__main__":
    main()
