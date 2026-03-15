"""Fast smoke runner for high-risk user-facing flows.

This is intentionally smaller and faster than the full pytest suite.
It targets the paths that most often regress during rapid iteration:
onboarding imports, assistant task actions, due-date normalization,
review insights, and song recommendation cache behavior.
"""

from __future__ import annotations

import os
import sys
from uuid import uuid4


SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SERVER_DIR)

os.environ["DATABASE_URL"] = "sqlite:///smoke_user_flows.db"
os.environ["LLM_PROVIDER"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402

from api_v2.main import app, _rate_buckets  # noqa: E402
from core.time import local_date_offset_iso  # noqa: E402
from database.db import get_db, init_db  # noqa: E402
from database.models import Task  # noqa: E402


init_db()
client = TestClient(app)


def _username(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def login(name: str, password: str = "smoke-pass") -> None:
    _rate_buckets.clear()
    client.headers.pop("X-Session-Token", None)
    res = client.post("/api/session/login", json={"display_name": name, "password": password})
    assert res.status_code == 200, res.text
    client.headers["X-Session-Token"] = res.json()["session_token"]


def case_onboarding_commitments_infer_real_recurrence() -> None:
    login(_username("smoke-onboarding"))
    res = client.post(
        "/api/onboarding/complete",
        json={
            "commitments": "每天遛狗\n每周组会",
            "goals": "完成作品集",
            "brain_dump": "",
            "daily_capacity": 6,
            "lang": "zh",
        },
    )
    assert res.status_code == 201, res.text
    tasks = client.get("/api/tasks?status=active").json()
    task_map = {task["title"]: task for task in tasks}
    assert task_map["每天遛狗"]["task_kind"] == "daily"
    assert task_map["每周组会"]["task_kind"] == "weekly"
    assert task_map["每周组会"]["recurrence_weekday"] is None
    assert task_map["完成作品集"]["task_kind"] == "temporary"


def case_onboarding_plain_commitments_remain_daily() -> None:
    login(_username("smoke-plain-daily"))
    res = client.post(
        "/api/onboarding/complete",
        json={
            "commitments": "吃饭\n睡觉\nleetcode",
            "goals": "",
            "brain_dump": "",
            "daily_capacity": 6,
            "lang": "zh",
        },
    )
    assert res.status_code == 201, res.text
    tasks = client.get("/api/tasks?status=active").json()
    task_map = {task["title"]: task for task in tasks}
    assert task_map["吃饭"]["task_kind"] == "daily"
    assert task_map["睡觉"]["task_kind"] == "daily"
    assert task_map["leetcode"]["task_kind"] == "daily"


def case_manual_weekly_task_is_not_treated_as_daily() -> None:
    login(_username("smoke-weekly"))
    created = client.post("/api/tasks", json={"title": "每周三meeting"})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["task_kind"] == "weekly"
    assert body["recurrence_weekday"] == 2


def case_weekday_phrase_without_meizhou_is_weekly() -> None:
    login(_username("smoke-weekday-phrase"))
    created = client.post("/api/tasks", json={"title": "周三有个会议"})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["task_kind"] == "weekly"
    assert body["recurrence_weekday"] == 2


def case_assistant_normalizes_month_day_due_date() -> None:
    login(_username("smoke-ddl"))
    created = client.post("/api/tasks", json={"title": "完成capstone", "task_kind": "temporary"})
    assert created.status_code == 201, created.text
    reply = client.post("/api/assistant/chat", json={"message": "帮我把capstone的ddl设置到3.17", "lang": "zh"})
    assert reply.status_code == 200, reply.text
    tasks = client.get("/api/tasks?status=active").json()
    task = next(item for item in tasks if item["title"] == "完成capstone")
    assert task["due_date"] == "2026-03-17"


def case_list_tasks_cleans_legacy_month_day_due_date() -> None:
    login(_username("smoke-legacy-date"))
    created = client.post("/api/tasks", json={"title": "legacy ddl", "task_kind": "temporary"})
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    with get_db() as db:
        task = db.get(Task, task_id)
        task.due_date = "3.17"
        db.flush()
    tasks = client.get("/api/tasks?status=active").json()
    task = next(item for item in tasks if item["id"] == task_id)
    assert task["due_date"] == "2026-03-17"


def case_assistant_handles_natural_adds_zh_and_en() -> None:
    login(_username("smoke-natural"))
    zh = client.post("/api/assistant/chat", json={"message": "我要吃饭", "lang": "zh"})
    assert zh.status_code == 200, zh.text
    en = client.post("/api/assistant/chat", json={"message": "I need to sleep", "lang": "en"})
    assert en.status_code == 200, en.text
    tasks = client.get("/api/tasks?status=active").json()
    titles = {task["title"] for task in tasks}
    assert "吃饭" in titles
    assert "sleep" in titles


def case_review_insights_return_non_empty_text() -> None:
    login(_username("smoke-review"))
    task = client.post("/api/tasks", json={"title": "write summary", "task_kind": "temporary"})
    assert task.status_code == 201, task.text
    task_id = task.json()["id"]
    assert client.post("/api/mood", json={"mood_level": 2, "note": "今天状态有点散"}).status_code == 200
    assert client.post(
        "/api/focus/sessions",
        json={"task_id": task_id, "duration_minutes": 25, "session_type": "work"},
    ).status_code == 200
    assert client.put(f"/api/tasks/{task_id}", json={"status": "completed"}).status_code == 200
    review = client.get(
        f"/api/review-insights?date={local_date_offset_iso(0)}&month={local_date_offset_iso(0)[:7]}&lang=zh"
    )
    assert review.status_code == 200, review.text
    body = review.json()
    assert body["daily"]
    assert body["weekly"]
    assert body["monthly"]


def case_song_recommendation_cache_path_is_stable() -> None:
    login(_username("smoke-songs"))
    assert client.post("/api/tasks", json={"title": "Write thesis draft", "priority": 5}).status_code == 201
    assert client.post("/api/mood", json={"mood_level": 2, "note": "need calm focus"}).status_code == 200
    first = client.get("/api/songs/recommend?lang=en")
    second = client.get("/api/songs/recommend?lang=en")
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["songs"] == second.json()["songs"]


def main() -> None:
    cases = [
        ("onboarding recurrence import", case_onboarding_commitments_infer_real_recurrence),
        ("onboarding plain commitments stay daily", case_onboarding_plain_commitments_remain_daily),
        ("manual weekly recurrence", case_manual_weekly_task_is_not_treated_as_daily),
        ("weekday phrase recurrence", case_weekday_phrase_without_meizhou_is_weekly),
        ("assistant month/day ddl", case_assistant_normalizes_month_day_due_date),
        ("list tasks cleans legacy month/day", case_list_tasks_cleans_legacy_month_day_due_date),
        ("assistant natural adds", case_assistant_handles_natural_adds_zh_and_en),
        ("review insights non-empty", case_review_insights_return_non_empty_text),
        ("song cache stable", case_song_recommendation_cache_path_is_stable),
    ]

    print("Running smoke user flows...")
    passed = 0
    for label, fn in cases:
        fn()
        passed += 1
        print(f"PASS: {label}")
    print(f"Smoke complete: {passed}/{len(cases)} passed")


if __name__ == "__main__":
    main()
