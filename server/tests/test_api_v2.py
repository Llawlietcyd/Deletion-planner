import json
import os
import sys
from uuid import uuid4
from core.time import local_date_offset_iso, next_month_iso, next_weekday_iso, normalize_date_string, upcoming_weekday_iso, upcoming_weekend_iso

# Ensure server directory is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "sqlite:///test_v2.db"
os.environ["LLM_PROVIDER"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402
from api_v2.main import app, _rate_buckets  # noqa: E402
from database.db import init_db  # noqa: E402

init_db()
client = TestClient(app)


def login_as(username="demo-user", password="demo-pass"):
    _rate_buckets.clear()
    client.headers.pop("X-Session-Token", None)
    res = client.post("/api/session/login", json={"display_name": username, "password": password})
    assert res.status_code == 200
    token = res.json()["session_token"]
    client.headers["X-Session-Token"] = token
    return token


def unique_username(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def ensure_assistant_ready(lang="en"):
    res = client.get(f"/api/assistant/state?lang={lang}")
    assert res.status_code == 200
    assert res.json()["profile_completed"] is True
    return res


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_session_and_onboarding_flow():
    client.headers.pop("X-Session-Token", None)
    session = client.get("/api/session")
    assert session.status_code == 200
    assert session.json()["logged_in"] is False

    login = client.post(
        "/api/session/login",
        json={"display_name": unique_username("demo-user"), "password": "demo-pass"},
    )
    assert login.status_code == 200
    assert login.json()["logged_in"] is True
    assert login.json()["display_name"].startswith("demo-user-")
    assert login.json()["has_password"] is True
    client.headers["X-Session-Token"] = login.json()["session_token"]

    onboarding = client.post(
        "/api/onboarding/complete",
        json={
            "commitments": "Capstone presentation !urgent",
            "goals": "Ship the prototype",
            "brain_dump": "Clean task copy\nReply to mentor",
            "daily_capacity": 5,
            "lang": "en",
        },
    )
    assert onboarding.status_code == 201
    body = onboarding.json()
    assert body["created_task_count"] == 4
    assert body["session"]["onboarding_completed"] is True
    assert body["plan"]["capacity_summary"]["capacity_units"] == 5


def test_login_rejects_invalid_birthday():
    client.headers.pop("X-Session-Token", None)
    _rate_buckets.clear()
    res = client.post(
        "/api/session/login",
        json={
            "display_name": unique_username("bad-birthday"),
            "password": "demo-pass",
            "birthday": "123456789",
        },
    )
    assert res.status_code == 400
    assert res.json()["error_code"] == "INVALID_BIRTHDAY"


def test_onboarding_commitments_become_daily_tasks():
    login = client.post(
        "/api/session/login",
        json={"display_name": unique_username("onboarding-daily"), "password": "demo-pass"},
    )
    assert login.status_code == 200
    client.headers["X-Session-Token"] = login.json()["session_token"]

    onboarding = client.post(
        "/api/onboarding/complete",
        json={
            "commitments": "每天遛狗\n每周组会",
            "goals": "完成作品集",
            "brain_dump": "",
            "daily_capacity": 6,
            "lang": "zh",
        },
    )
    assert onboarding.status_code == 201

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    rows = tasks.json()
    dog = next(task for task in rows if task["title"] == "每天遛狗")
    sync = next(task for task in rows if task["title"] == "每周组会")
    goal = next(task for task in rows if task["title"] == "完成作品集")
    assert dog["task_kind"] == "daily"
    assert sync["task_kind"] == "weekly"
    assert sync["recurrence_weekday"] is None
    assert goal["task_kind"] == "temporary"


def test_onboarding_plain_commitments_stay_daily():
    login = client.post(
        "/api/session/login",
        json={"display_name": unique_username("onboarding-plain"), "password": "demo-pass"},
    )
    assert login.status_code == 200
    client.headers["X-Session-Token"] = login.json()["session_token"]

    onboarding = client.post(
        "/api/onboarding/complete",
        json={
            "commitments": "吃饭\n睡觉\nleetcode",
            "goals": "",
            "brain_dump": "",
            "daily_capacity": 6,
            "lang": "zh",
        },
    )
    assert onboarding.status_code == 201

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    rows = {task["title"]: task for task in tasks.json()}
    assert rows["吃饭"]["task_kind"] == "daily"
    assert rows["睡觉"]["task_kind"] == "daily"
    assert rows["leetcode"]["task_kind"] == "daily"


def test_onboarding_weekday_phrase_without_meizhou_becomes_weekly():
    login = client.post(
        "/api/session/login",
        json={"display_name": unique_username("onboarding-weekday-phrase"), "password": "demo-pass"},
    )
    assert login.status_code == 200
    client.headers["X-Session-Token"] = login.json()["session_token"]

    onboarding = client.post(
        "/api/onboarding/complete",
        json={
            "commitments": "周三有个会议\n每天吃饭",
            "goals": "",
            "brain_dump": "",
            "daily_capacity": 6,
            "lang": "zh",
        },
    )
    assert onboarding.status_code == 201

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    rows = {task["title"]: task for task in tasks.json()}
    assert rows["周三有个会议"]["task_kind"] == "weekly"
    assert rows["周三有个会议"]["recurrence_weekday"] == 2
    assert rows["每天吃饭"]["task_kind"] == "daily"


def test_manual_plain_weekday_phrase_becomes_weekly():
    login_as(unique_username("manual-weekday-weekly"), "manual-pass")

    created = client.post("/api/tasks", json={"title": "周三有个会"})
    assert created.status_code == 201
    body = created.json()
    assert body["task_kind"] == "weekly"
    assert body["recurrence_weekday"] == 2
    assert body["due_date"] is None


def test_assistant_adds_english_weekly_recurring_task():
    login_as(unique_username("assistant-weekly-en"), "assistant-pass")
    ensure_assistant_ready("en")

    reply = client.post(
        "/api/assistant/chat",
        json={"message": "i have plan on every monday to play game with my friends", "lang": "en"},
    )
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    created = next(
        task for task in tasks.json()
        if "play game" in task["title"].lower() and "friend" in task["title"].lower()
    )
    assert created["task_kind"] == "weekly"
    assert created["recurrence_weekday"] == 0


def test_assistant_plain_weekday_phrase_becomes_weekly():
    login_as(unique_username("assistant-weekday-weekly"), "assistant-pass")
    ensure_assistant_ready("zh")

    reply = client.post(
        "/api/assistant/chat",
        json={"message": "我周三有个会", "lang": "zh"},
    )
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    created = next(task for task in tasks.json() if task["title"] == "会")
    assert created["task_kind"] == "weekly"
    assert created["recurrence_weekday"] == 2
    assert created["due_date"] is None


def test_assistant_relative_weekend_phrase_strips_shell_and_becomes_one_off():
    login_as(unique_username("assistant-weekly-title-clean"), "assistant-pass")
    ensure_assistant_ready("zh")

    reply = client.post(
        "/api/assistant/chat",
        json={"message": "这周日有个pre", "lang": "zh"},
    )
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    created = next(task for task in tasks.json() if task["title"] == "pre")
    assert created["task_kind"] == "temporary"
    assert created["recurrence_weekday"] is None
    assert created["due_date"] is not None


def test_assistant_relative_weekday_phrase_becomes_one_off_due_date():
    login_as(unique_username("assistant-relative-weekday"), "assistant-pass")
    ensure_assistant_ready("zh")

    reply = client.post(
        "/api/assistant/chat",
        json={"message": "这周五我要去peter家", "lang": "zh"},
    )
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    created = next(task for task in tasks.json() if task["title"] == "去peter家")
    assert created["task_kind"] == "temporary"
    assert created["recurrence_weekday"] is None
    assert created["due_date"] is not None


def test_assistant_adds_two_weekly_tasks_for_multiple_english_weekdays():
    login_as(unique_username("assistant-weekly-en-multi"), "assistant-pass")
    ensure_assistant_ready("en")

    reply = client.post(
        "/api/assistant/chat",
        json={"message": "i have plan on every monday and thursday to play game with my friends", "lang": "en"},
    )
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    created = [
        task for task in tasks.json()
        if "play game" in task["title"].lower() and "friend" in task["title"].lower()
    ]
    assert len(created) == 2
    weekdays = sorted(task["recurrence_weekday"] for task in created)
    assert weekdays == [0, 3]


def test_assistant_adds_english_weekly_recurring_task_without_on_keyword():
    login_as(unique_username("assistant-weekly-en-no-on"), "assistant-pass")
    ensure_assistant_ready("en")

    reply = client.post(
        "/api/assistant/chat",
        json={"message": "i have a plan every monday to drink water 2L", "lang": "en"},
    )
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    created = next(task for task in tasks.json() if "drink water 2l" in task["title"].lower())
    assert created["task_kind"] == "weekly"
    assert created["recurrence_weekday"] == 0


def test_assistant_adds_english_one_off_task_with_plain_weekday_due_date():
    login_as(unique_username("assistant-plain-weekday-en"), "assistant-pass")
    ensure_assistant_ready("en")

    reply = client.post(
        "/api/assistant/chat",
        json={"message": "I need to submit report on friday", "lang": "en"},
    )
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    created = next(task for task in tasks.json() if task["title"] == "submit report")
    assert created["task_kind"] == "temporary"
    assert created["recurrence_weekday"] is None
    assert created["due_date"] == upcoming_weekday_iso(4)


def test_manual_plural_english_weekday_phrase_becomes_weekly():
    login_as(unique_username("manual-plural-weekday-en"), "manual-pass")

    created = client.post("/api/tasks", json={"title": "Part-time job on Tuesdays"})
    assert created.status_code == 201
    body = created.json()
    assert body["task_kind"] == "weekly"
    assert body["recurrence_weekday"] == 1
    assert body["due_date"] is None


def test_manual_relative_english_weekday_phrase_becomes_one_off_due_date():
    login_as(unique_username("manual-relative-weekday-en"), "manual-pass")

    created = client.post("/api/tasks", json={"title": "Exam next Monday"})
    assert created.status_code == 201
    body = created.json()
    assert body["task_kind"] == "temporary"
    assert body["recurrence_weekday"] is None
    assert body["due_date"] == next_weekday_iso(0)


def test_list_tasks_self_heals_legacy_plural_weekday_task():
    login_as(unique_username("legacy-plural-weekday"), "manual-pass")

    created = client.post("/api/tasks", json={"title": "Part-time job on Tuesdays", "task_kind": "daily"})
    assert created.status_code == 201
    task_id = created.json()["id"]

    from database.db import get_db
    from database.models import Task
    with get_db() as db:
        task = db.get(Task, task_id)
        task.task_kind = "daily"
        task.recurrence_weekday = None
        task.due_date = None
        db.flush()

    listed = client.get("/api/tasks?status=active")
    assert listed.status_code == 200
    healed = next(task for task in listed.json() if task["id"] == task_id)
    assert healed["task_kind"] == "weekly"
    assert healed["recurrence_weekday"] == 1
    assert healed["due_date"] is None


def test_list_tasks_self_heals_legacy_relative_weekday_task():
    login_as(unique_username("legacy-relative-weekday"), "manual-pass")

    created = client.post("/api/tasks", json={"title": "Exam next Monday", "task_kind": "weekly", "recurrence_weekday": 0})
    assert created.status_code == 201
    task_id = created.json()["id"]

    from database.db import get_db
    from database.models import Task
    with get_db() as db:
        task = db.get(Task, task_id)
        task.task_kind = "weekly"
        task.recurrence_weekday = 0
        task.due_date = None
        db.flush()

    listed = client.get("/api/tasks?status=active")
    assert listed.status_code == 200
    healed = next(task for task in listed.json() if task["id"] == task_id)
    assert healed["task_kind"] == "temporary"
    assert healed["recurrence_weekday"] is None
    assert healed["due_date"] == next_weekday_iso(0)


def test_assistant_adds_chinese_one_off_task_with_relative_day_prefix():
    login_as(unique_username("assistant-relative-day-zh"), "assistant-pass")
    ensure_assistant_ready("zh")

    reply = client.post(
        "/api/assistant/chat",
        json={"message": "我要明天交论文", "lang": "zh"},
    )
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    created = next(task for task in tasks.json() if task["title"] == "交论文")
    assert created["task_kind"] == "temporary"
    assert created["recurrence_weekday"] is None
    assert created["due_date"] == local_date_offset_iso(1)


def test_assistant_adds_english_one_off_task_with_explicit_date_suffix():
    login_as(unique_username("assistant-explicit-date-en"), "assistant-pass")
    ensure_assistant_ready("en")

    reply = client.post(
        "/api/assistant/chat",
        json={"message": "I need to submit report 3/17", "lang": "en"},
    )
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    created = next(task for task in tasks.json() if task["title"] == "submit report")
    assert created["task_kind"] == "temporary"
    assert created["recurrence_weekday"] is None
    assert created["due_date"] == normalize_date_string("3/17")


def test_completing_daily_task_keeps_it_active_for_future_days():
    login_as(unique_username("daily-complete-persists"), "daily-pass")
    task = client.post("/api/tasks", json={"title": "吃饭", "task_kind": "daily"})
    assert task.status_code == 201
    task_id = task.json()["id"]

    completed = client.put(f"/api/tasks/{task_id}", json={"status": "completed"})
    assert completed.status_code == 200
    body = completed.json()
    assert body["task_kind"] == "daily"
    assert body["status"] == "active"
    assert body["completed_at"] is not None

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    persisted = next(item for item in tasks.json() if item["id"] == task_id)
    assert persisted["status"] == "active"
    assert persisted["completion_count"] == 1


def test_recurring_task_complete_can_be_restored_without_double_counting():
    login_as(unique_username("daily-restore"), "daily-pass")
    task = client.post("/api/tasks", json={"title": "喝水", "task_kind": "daily"})
    assert task.status_code == 201
    task_id = task.json()["id"]

    first_complete = client.put(f"/api/tasks/{task_id}", json={"status": "completed"})
    assert first_complete.status_code == 200
    assert first_complete.json()["completion_count"] == 1
    assert first_complete.json()["completed_at"] is not None

    second_complete = client.put(f"/api/tasks/{task_id}", json={"status": "completed"})
    assert second_complete.status_code == 200
    assert second_complete.json()["completion_count"] == 1

    restored = client.put(f"/api/tasks/{task_id}", json={"status": "active"})
    assert restored.status_code == 200
    assert restored.json()["completed_at"] is None
    assert restored.json()["completion_count"] == 1


def test_assistant_next_month_is_not_confused_with_next_monday_prefix():
    login_as(unique_username("assistant-next-month"), "assistant-pass")
    ensure_assistant_ready("en")
    created = client.post("/api/tasks", json={"title": "finish capstone demo", "task_kind": "temporary"})
    assert created.status_code == 201

    reply = client.post(
        "/api/assistant/chat",
        json={"message": "Postpone finish capstone demo to next month", "lang": "en"},
    )
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active").json()
    task = next(item for item in tasks if item["title"] == "finish capstone demo")
    assert task["due_date"] == next_month_iso()


def test_updating_weekly_title_recomputes_weekday():
    login_as(unique_username("weekly-retitle"), "weekly-pass")
    created = client.post("/api/tasks", json={"title": "周三有个会议"})
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert created.json()["task_kind"] == "weekly"
    assert created.json()["recurrence_weekday"] == 2

    updated = client.put(f"/api/tasks/{task_id}", json={"title": "周四有个会议"})
    assert updated.status_code == 200
    body = updated.json()
    assert body["task_kind"] == "weekly"
    assert body["recurrence_weekday"] == 3


def test_task_lifecycle():
    login_as("task-user")
    create = client.post(
        "/api/tasks",
        json={"title": "Write integration test", "priority": 3, "category": "core"},
    )
    assert create.status_code == 201
    task_id = create.json()["id"]

    listed = client.get("/api/tasks?status=active")
    assert listed.status_code == 200
    assert any(t["id"] == task_id for t in listed.json())

    complete = client.put(f"/api/tasks/{task_id}", json={"status": "completed"})
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"


def test_task_restore():
    """Restoring a completed/deleted task should clear timestamps."""
    login_as("restore-user")
    create = client.post("/api/tasks", json={"title": "Restore test"})
    task_id = create.json()["id"]

    client.put(f"/api/tasks/{task_id}", json={"status": "completed"})
    res = client.put(f"/api/tasks/{task_id}", json={"status": "active"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "active"
    assert data["completed_at"] is None
    assert data["deleted_at"] is None


def test_task_with_due_date():
    """Creating and updating tasks with due_date."""
    login_as("due-user")
    create = client.post(
        "/api/tasks",
        json={"title": "Due date test", "due_date": "2025-12-31"},
    )
    assert create.status_code == 201
    assert create.json()["due_date"] == "2025-12-31"

    task_id = create.json()["id"]
    update = client.put(f"/api/tasks/{task_id}", json={"due_date": "2025-06-15"})
    assert update.json()["due_date"] == "2025-06-15"

    clear = client.put(f"/api/tasks/{task_id}", json={"due_date": ""})
    assert clear.json()["due_date"] is None


def test_task_kind_inference_and_update():
    login_as("kind-user", "kind-pass")
    daily = client.post("/api/tasks", json={"title": "Daily workout #daily"})
    assert daily.status_code == 201
    assert daily.json()["task_kind"] == "daily"

    temp = client.post("/api/tasks", json={"title": "Finish visa form", "due_date": "2026-03-20"})
    assert temp.status_code == 201
    assert temp.json()["task_kind"] == "temporary"

    task_id = temp.json()["id"]
    updated = client.put(f"/api/tasks/{task_id}", json={"task_kind": "daily"})
    assert updated.status_code == 200
    assert updated.json()["task_kind"] == "daily"


def test_weekly_task_inference_and_legacy_cleanup():
    login_as("weekly-kind-user", "kind-pass")
    weekly = client.post("/api/tasks", json={"title": "每周三meeting"})
    assert weekly.status_code == 201
    assert weekly.json()["task_kind"] == "weekly"
    assert weekly.json()["recurrence_weekday"] == 2

    daily_like = client.post("/api/tasks", json={"title": "每周五钢琴课", "task_kind": "daily"})
    assert daily_like.status_code == 201

    listed = client.get("/api/tasks?status=active")
    assert listed.status_code == 200
    piano = next(task for task in listed.json() if task["title"] == "每周五钢琴课")
    assert piano["task_kind"] == "weekly"
    assert piano["recurrence_weekday"] == 4


def test_weekday_phrase_without_meizhou_still_becomes_weekly():
    login_as("weekday-phrase-user", "kind-pass")
    created = client.post("/api/tasks", json={"title": "周三有个会议"})
    assert created.status_code == 201
    body = created.json()
    assert body["task_kind"] == "weekly"
    assert body["recurrence_weekday"] == 2


def test_search_tasks():
    """Search tasks by keyword."""
    login_as("search-user")
    client.post("/api/tasks", json={"title": "Learn Python basics"})
    client.post("/api/tasks", json={"title": "Buy groceries"})

    res = client.get("/api/tasks?status=active&q=Python")
    assert res.status_code == 200
    results = res.json()
    assert any("Python" in t["title"] for t in results)
    assert not any("groceries" in t["title"] for t in results)


def test_batch_create_with_markers():
    """Batch create should parse priority and due date markers."""
    login_as("batch-user")
    text = "Write report !high\nRead article @tomorrow\nFix bug !urgent @2025-03-20"
    res = client.post("/api/tasks/batch", json={"text": text})
    assert res.status_code == 201
    tasks = res.json()
    assert len(tasks) == 3
    assert tasks[0]["priority"] == 3  # !high
    assert tasks[1]["due_date"] is not None  # @tomorrow
    assert tasks[2]["priority"] == 5  # !urgent
    assert tasks[2]["due_date"] == "2025-03-20"


def test_capacity_aware_plan_generation():
    login_as("plan-user")
    client.post("/api/tasks", json={"title": "Client deadline brief", "priority": 5})
    client.post("/api/tasks", json={"title": "Optional refactor idea", "priority": 0})
    client.post("/api/tasks", json={"title": "Read article someday", "priority": 0})

    res = client.post(
        "/api/plans/generate",
        json={"lang": "en", "capacity_units": 2},
    )
    assert res.status_code in (200, 201)
    body = res.json()

    assert "capacity_summary" in body
    assert body["capacity_summary"]["capacity_units"] == 2
    assert "deletion_suggestions" in body


def test_completed_plan_task_disappears_from_today_view():
    login_as("today-user")
    client.post("/api/tasks", json={"title": "Finish draft", "priority": 5})
    client.post("/api/tasks", json={"title": "Read optional note", "priority": 0})

    generated = client.post("/api/plans/generate", json={"lang": "en", "capacity_units": 3, "force": True})
    assert generated.status_code in (200, 201)
    today = generated.json()
    assert len(today["tasks"]) >= 1

    plan_task_id = today["tasks"][0]["id"]
    feedback = client.post(
        "/api/feedback",
        json={
            "date": today["date"],
            "results": [{"plan_task_id": plan_task_id, "status": "completed"}],
            "lang": "en",
            "capacity_units": 3,
        },
    )
    assert feedback.status_code == 200

    refreshed = client.get("/api/plans/today?lang=en&capacity_units=3")
    assert refreshed.status_code == 200
    refreshed_tasks = refreshed.json()["tasks"]
    assert all(task["id"] != plan_task_id for task in refreshed_tasks)


def test_reorder_tasks():
    login_as("reorder-user")
    t1 = client.post("/api/tasks", json={"title": "Reorder A"}).json()["id"]
    t2 = client.post("/api/tasks", json={"title": "Reorder B"}).json()["id"]
    t3 = client.post("/api/tasks", json={"title": "Reorder C"}).json()["id"]

    res = client.put("/api/tasks/reorder", json={"ordered_task_ids": [t3, t1, t2]})
    assert res.status_code == 200
    assert res.json()["count"] == 3


def test_history_pagination():
    login_as("history-user")
    res = client.get("/api/history?limit=5&offset=0")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_weekly_summary():
    login_as("weekly-user")
    res = client.get("/api/weekly-summary?lang=en")
    assert res.status_code == 200
    body = res.json()
    assert "summary" in body
    assert "completion_rate" in body


def test_llm_settings():
    login_as("settings-user")
    res = client.get("/api/settings/llm")
    assert res.status_code == 200
    assert "provider" in res.json()

    deepseek = client.put("/api/settings/llm", json={"model": "deepseek-chat"})
    assert deepseek.status_code == 200
    assert deepseek.json()["provider"] == "deepseek"
    assert deepseek.json()["model"] == "deepseek-chat"

    test = client.post("/api/settings/llm/test")
    assert test.status_code == 200
    assert "ok" in test.json()


def test_stats():
    login_as("stats-user")
    res = client.get("/api/stats")
    assert res.status_code == 200
    body = res.json()
    assert "active_tasks" in body
    assert "completion_rate" in body


def test_mood_history_keeps_multiple_real_timestamps():
    login_as("mood-user")
    first = client.post("/api/mood", json={"mood_level": 2, "note": "morning slump"})
    assert first.status_code == 200
    second = client.post("/api/mood", json={"mood_level": 4, "note": "afternoon recovery"})
    assert second.status_code == 200

    today = client.get("/api/mood/today")
    assert today.status_code == 200
    assert today.json()["mood_level"] == 4
    assert today.json()["note"] == "afternoon recovery"

    history = client.get("/api/mood/history?days=7")
    assert history.status_code == 200
    rows = history.json()
    assert len(rows) >= 2
    assert rows[0]["created_at"] is not None
    assert rows[0]["created_at"].endswith("+00:00")
    assert rows[0]["mood_level"] == 4
    assert rows[1]["mood_level"] == 2


def test_fortune_cache_respects_language():
    login_as("fortune-user", "fortune-pass")

    zh = client.post("/api/fortune/daily?lang=zh")
    assert zh.status_code == 200
    assert zh.json()["lang"] == "zh"

    mismatch = client.get("/api/fortune/today?lang=en")
    assert mismatch.status_code == 200
    assert mismatch.json()["generated"] is False

    en = client.post("/api/fortune/daily?lang=en")
    assert en.status_code == 200
    assert en.json()["lang"] == "en"

    cached = client.get("/api/fortune/today?lang=en")
    assert cached.status_code == 200
    assert cached.json()["generated"] is True
    assert cached.json()["lang"] == "en"


def test_developer_reset_clears_local_data():
    login_as("reset-user", "reset-pass")
    client.post("/api/tasks", json={"title": "Reset me"})
    client.post("/api/mood", json={"mood_level": 3, "note": "temporary"})

    reset = client.post("/api/settings/developer/reset")
    assert reset.status_code == 200
    assert reset.json()["ok"] is True

    session = client.get("/api/session")
    assert session.status_code == 200
    assert session.json()["logged_in"] is False


def test_developer_reset_preserves_protected_showcase_account():
    login_as("chen", "123456")
    client.post("/api/tasks", json={"title": "Protected showcase task"})
    client.post("/api/mood", json={"mood_level": 4, "note": "protected mood"})

    login_as("reset-other-user", "reset-pass")
    client.post("/api/tasks", json={"title": "Temporary reset task"})

    reset = client.post("/api/settings/developer/reset")
    assert reset.status_code == 200
    assert reset.json()["ok"] is True
    assert "preserved" in reset.json()["message"].lower()

    login_as("chen", "123456")
    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    assert any(task["title"] == "Protected showcase task" for task in tasks.json())

    mood = client.get("/api/mood/today")
    assert mood.status_code == 200
    assert mood.json()["note"] == "protected mood"


def test_song_recommendations_use_active_tasks_without_plan():
    login_as("songs-user", "songs-pass")
    client.post("/api/tasks", json={"title": "Write thesis draft", "priority": 5})
    client.post("/api/tasks", json={"title": "Prepare portfolio", "priority": 3})
    client.post("/api/mood", json={"mood_level": 2, "note": "need calm focus"})

    res = client.get("/api/songs/recommend?lang=en")
    assert res.status_code == 200
    body = res.json()
    assert body["focus_task"] == "Write thesis draft"
    assert "Write thesis draft" in body["top_tasks"]
    assert len(body["songs"]) >= 1


def test_song_recommendations_refresh_token_changes_mock_results():
    login_as("songs-refresh-user", "songs-pass")
    client.post("/api/tasks", json={"title": "Write thesis draft", "priority": 5})
    client.post("/api/mood", json={"mood_level": 2, "note": "need calm focus"})

    first = client.get("/api/songs/recommend?lang=en&refresh_token=alpha")
    second = client.get("/api/songs/recommend?lang=en&refresh_token=beta")
    assert first.status_code == 200
    assert second.status_code == 200
    first_names = [song["name"] for song in first.json()["songs"]]
    second_names = [song["name"] for song in second.json()["songs"]]
    assert first_names != second_names


def test_song_recommendations_zero_refresh_token_keeps_cache_path():
    login_as("songs-zero-refresh-user", "songs-pass")
    client.post("/api/tasks", json={"title": "Write thesis draft", "priority": 5})
    client.post("/api/mood", json={"mood_level": 2, "note": "need calm focus"})

    first = client.get("/api/songs/recommend?lang=en&refresh_token=0")
    second = client.get("/api/songs/recommend?lang=en&refresh_token=0")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["songs"] == second.json()["songs"]


def test_multiple_accounts_are_isolated():
    login_as("alpha", "alpha-pass")
    client.post("/api/tasks", json={"title": "Alpha private task"})

    login_as("beta", "beta-pass")
    client.post("/api/tasks", json={"title": "Beta private task"})
    beta_tasks = client.get("/api/tasks?status=active").json()
    assert any(task["title"] == "Beta private task" for task in beta_tasks)
    assert not any(task["title"] == "Alpha private task" for task in beta_tasks)

    login_as("alpha", "alpha-pass")
    alpha_tasks = client.get("/api/tasks?status=active").json()
    assert any(task["title"] == "Alpha private task" for task in alpha_tasks)


def test_parallel_sessions_keep_users_separate():
    client_a = TestClient(app)
    client_b = TestClient(app)

    login_a = client_a.post("/api/session/login", json={"display_name": "window-a", "password": "pass-a"})
    login_b = client_b.post("/api/session/login", json={"display_name": "window-b", "password": "pass-b"})
    token_a = login_a.json()["session_token"]
    token_b = login_b.json()["session_token"]
    client_a.headers["X-Session-Token"] = token_a
    client_b.headers["X-Session-Token"] = token_b

    client_a.post("/api/tasks", json={"title": "Task from A"})
    client_b.post("/api/tasks", json={"title": "Task from B"})

    tasks_a = client_a.get("/api/tasks?status=active").json()
    tasks_b = client_b.get("/api/tasks?status=active").json()

    assert any(task["title"] == "Task from A" for task in tasks_a)
    assert not any(task["title"] == "Task from B" for task in tasks_a)
    assert any(task["title"] == "Task from B" for task in tasks_b)
    assert not any(task["title"] == "Task from A" for task in tasks_b)


def test_assistant_is_ready_on_first_open():
    login_as(unique_username("assistant-profile"), "assistant-pass")

    state = ensure_assistant_ready("zh")
    body = state.json()
    assert len(body["messages"]) >= 1
    assert any("私人管家" in message["content"] for message in body["messages"] if message["role"] == "assistant")


def test_assistant_can_add_task_and_refresh_plan():
    login_as(unique_username("assistant-actions"), "assistant-pass")
    ensure_assistant_ready("en")

    reply = client.post("/api/assistant/chat", json={"message": "Add task: send mentor update", "lang": "en"})
    assert reply.status_code == 200
    body = reply.json()
    assert body["profile_completed"] is True
    assert any("Added task" in message["content"] for message in body["messages"] if message["role"] == "assistant")

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    assert any(task["title"] == "send mentor update" for task in tasks.json())


def test_assistant_add_task_normalizes_chinese_title():
    login_as(unique_username("assistant-zh-add"), "assistant-pass")
    ensure_assistant_ready("zh")

    reply = client.post("/api/assistant/chat", json={"message": "加一个吃饭的任务", "lang": "zh"})
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    assert any(task["title"] == "吃饭" for task in tasks.json())


def test_assistant_add_task_normalizes_english_title():
    login_as(unique_username("assistant-en-add"), "assistant-pass")
    ensure_assistant_ready("en")

    reply = client.post("/api/assistant/chat", json={"message": "Add a task: eat lunch", "lang": "en"})
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    assert any(task["title"] == "eat lunch" for task in tasks.json())


def test_assistant_handles_common_english_commands_without_pending_hijack():
    login_as(unique_username("assistant-en-common"), "assistant-pass")
    ensure_assistant_ready("en")

    client.post("/api/assistant/chat", json={"message": "I need to eat lunch", "lang": "en"})
    client.post("/api/tasks", json={"title": "walk dog", "task_kind": "temporary"})
    client.post("/api/tasks", json={"title": "sleep", "task_kind": "temporary"})

    delete_reply = client.post("/api/assistant/chat", json={"message": "Delete sleep", "lang": "en"})
    assert delete_reply.status_code == 200
    delete_messages = [message["content"] for message in delete_reply.json()["messages"] if message["role"] == "assistant"]
    assert any("Deleted task: sleep" in message for message in delete_messages)
    assert not any(message.count("Deleted task: sleep") > 1 for message in delete_messages)

    defer_reply = client.post("/api/assistant/chat", json={"message": "Postpone walk dog", "lang": "en"})
    assert defer_reply.status_code == 200
    defer_messages = [message["content"] for message in defer_reply.json()["messages"] if message["role"] == "assistant"]
    assert any("Deferred task: walk dog" in message for message in defer_messages)

    mark_reply = client.post("/api/assistant/chat", json={"message": "Mark eat lunch as daily", "lang": "en"})
    assert mark_reply.status_code == 200
    mark_messages = [message["content"] for message in mark_reply.json()["messages"] if message["role"] == "assistant"]
    assert any("Updated task: eat lunch" in message for message in mark_messages)

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    eat_lunch = next(task for task in tasks.json() if task["title"] == "eat lunch")
    walk_dog = next(task for task in tasks.json() if task["title"] == "walk dog")
    assert eat_lunch["task_kind"] == "daily"
    assert walk_dog["due_date"] == local_date_offset_iso(1)


def test_assistant_analysis_and_least_useful_are_handled_explicitly():
    login_as(unique_username("assistant-analysis"), "assistant-pass")
    ensure_assistant_ready("en")

    reply = client.post("/api/assistant/chat", json={"message": "Analyze my recent focus and completion pattern", "lang": "en"})
    assert reply.status_code == 200
    messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("focus session" in message.lower() or "cold start" in message.lower() for message in messages)

    refuse = client.post("/api/assistant/chat", json={"message": "Delete the least useful task", "lang": "en"})
    assert refuse.status_code == 200
    refuse_messages = [message["content"] for message in refuse.json()["messages"] if message["role"] == "assistant"]
    assert any("won't decide" in message.lower() and "least useful" in message.lower() for message in refuse_messages)


def test_assistant_handles_compound_delete_then_add_in_zh():
    login_as(unique_username("assistant-compound-zh"), "assistant-pass")
    ensure_assistant_ready("zh")

    client.post("/api/tasks", json={"title": "给导师发邮件", "task_kind": "temporary"})
    reply = client.post("/api/assistant/chat", json={"message": "删掉给导师发邮件，再加一个准备面试", "lang": "zh"})
    assert reply.status_code == 200
    tasks = client.get("/api/tasks?status=all").json()
    assert any(task["title"] == "给导师发邮件" and task["status"] == "deleted" for task in tasks)
    assert any(task["title"] == "准备面试" and task["status"] == "active" for task in tasks)


def test_assistant_handles_defer_to_tomorrow_phrasing():
    login_as(unique_username("assistant-defer-tomorrow"), "assistant-pass")
    ensure_assistant_ready("en")

    client.post("/api/tasks", json={"title": "buy groceries", "task_kind": "temporary"})
    reply = client.post("/api/assistant/chat", json={"message": "Postpone buy groceries to tomorrow", "lang": "en"})
    assert reply.status_code == 200
    tasks = client.get("/api/tasks?status=active").json()
    groceries = next(task for task in tasks if task["title"] == "buy groceries")
    assert groceries["due_date"] == local_date_offset_iso(1)


def test_assistant_handles_two_adds_in_one_sentence():
    login_as(unique_username("assistant-two-adds"), "assistant-pass")
    ensure_assistant_ready("zh")

    reply = client.post("/api/assistant/chat", json={"message": "我要睡觉，然后明天提醒我买咖啡", "lang": "zh"})
    assert reply.status_code == 200
    tasks = client.get("/api/tasks?status=active").json()
    assert any(task["title"] == "睡觉" for task in tasks)
    coffee = next(task for task in tasks if task["title"] == "买咖啡")
    assert coffee["due_date"] == local_date_offset_iso(1)


def test_assistant_does_not_duplicate_existing_task_on_natural_add():
    login_as(unique_username("assistant-no-dup"), "assistant-pass")
    ensure_assistant_ready("en")

    client.post("/api/tasks", json={"title": "sleep", "task_kind": "temporary"})
    reply = client.post("/api/assistant/chat", json={"message": "I need to sleep", "lang": "en"})
    assert reply.status_code == 200
    tasks = client.get("/api/tasks?status=active").json()
    sleep_tasks = [task for task in tasks if task["title"] == "sleep"]
    assert len(sleep_tasks) == 1


def test_assistant_natural_chinese_desire_creates_clean_task():
    login_as(unique_username("assistant-natural-zh"), "assistant-pass")
    ensure_assistant_ready("zh")

    reply = client.post("/api/assistant/chat", json={"message": "我要吃饭", "lang": "zh"})
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    assert any(task["title"] == "吃饭" for task in tasks.json())


def test_assistant_lists_tasks_without_internal_priority_markers():
    login_as(unique_username("assistant-list"), "assistant-pass")
    ensure_assistant_ready("zh")

    client.post("/api/tasks", json={"title": "遛狗", "task_kind": "temporary"})
    client.post("/api/tasks", json={"title": "睡觉", "task_kind": "temporary"})

    reply = client.post("/api/assistant/chat", json={"message": "我现在有哪些任务", "lang": "zh"})
    assert reply.status_code == 200
    assistant_messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("遛狗" in message and "睡觉" in message for message in assistant_messages)
    assert not any("[p" in message for message in assistant_messages)


def test_assistant_can_delete_task_with_spaced_compact_name():
    login_as(unique_username("assistant-spaced-delete"), "assistant-pass")
    client.post("/api/tasks", json={"title": "leetcode", "task_kind": "temporary"})

    reply = client.post("/api/assistant/chat", json={"message": "帮我删除 le e t co de", "lang": "zh"})
    assert reply.status_code == 200
    tasks = client.get("/api/tasks?status=all").json()
    leetcode = next(task for task in tasks if task["title"] == "leetcode")
    assert leetcode["status"] == "deleted"


def test_assistant_can_delete_task_with_natural_chinese_query_variation():
    login_as(unique_username("assistant-natural-delete"), "assistant-pass")
    client.post("/api/tasks", json={"title": "喝两升的水", "task_kind": "daily"})

    reply = client.post("/api/assistant/chat", json={"message": "帮我删除喝两升水的任务", "lang": "zh"})
    assert reply.status_code == 200
    assistant_messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("已删除任务：喝两升的水" in message for message in assistant_messages)

    tasks = client.get("/api/tasks?status=all").json()
    water = next(task for task in tasks if task["title"] == "喝两升的水")
    assert water["status"] == "deleted"


def test_assistant_followup_clarification_executes_directly():
    login_as(unique_username("assistant-followup-direct"), "assistant-pass")
    client.post("/api/tasks", json={"title": "leetcode easy", "task_kind": "temporary"})
    client.post("/api/tasks", json={"title": "leetcode hard", "task_kind": "temporary"})

    first = client.post("/api/assistant/chat", json={"message": "帮我删除 leetcode", "lang": "zh"})
    assert first.status_code == 200
    assert first.json()["pending"]["type"] == "task_choice"

    second = client.post("/api/assistant/chat", json={"message": "leetcode hard", "lang": "zh"})
    assert second.status_code == 200
    assistant_messages = [message["content"] for message in second.json()["messages"] if message["role"] == "assistant"]
    assert any("已删除任务：leetcode hard" in message for message in assistant_messages)


def test_list_tasks_cleans_legacy_concierge_titles():
    login_as(unique_username("assistant-cleanup"), "assistant-pass")
    created = client.post("/api/tasks", json={"title": "加一个睡觉的任务"})
    assert created.status_code == 201
    task_id = created.json()["id"]
    client.put(
        f"/api/tasks/{task_id}",
        json={"decision_reason": "Created by concierge."},
    )

    # FastAPI schema does not expose decision_reason writes, so patch directly via assistant flow style:
    from database.db import get_db
    from database.models import Task
    with get_db() as db:
        task = db.get(Task, task_id)
        task.decision_reason = "Created by concierge."
        db.flush()

    listed = client.get("/api/tasks?status=active")
    assert listed.status_code == 200
    assert any(task["title"] == "睡觉" for task in listed.json())


def test_list_tasks_hides_old_junk_concierge_titles():
    login_as(unique_username("assistant-cleanup-junk"), "assistant-pass")
    created = client.post("/api/tasks", json={"title": "Clarification: 我每周二都需要干嘛"})
    assert created.status_code == 201
    task_id = created.json()["id"]

    from database.db import get_db
    from database.models import Task
    with get_db() as db:
        task = db.get(Task, task_id)
        task.decision_reason = "Created by concierge."
        db.flush()

    listed = client.get("/api/tasks?status=active")
    assert listed.status_code == 200
    assert not any(task["id"] == task_id for task in listed.json())


def test_assistant_new_request_does_not_get_hijacked_by_pending_followup():
    login_as(unique_username("assistant-followup"), "assistant-pass")
    ensure_assistant_ready("zh")

    missing = client.post("/api/assistant/chat", json={"message": "删掉今天计划里最不重要的任务", "lang": "zh"})
    assert missing.status_code == 200

    fresh = client.post("/api/assistant/chat", json={"message": "帮我加上一个遛狗的日常活动", "lang": "zh"})
    assert fresh.status_code == 200
    body = fresh.json()

    assistant_messages = [message["content"] for message in body["messages"] if message["role"] == "assistant"]
    assert any("已添加任务：遛狗的日常活动" in message for message in assistant_messages)
    assert not any("Additional clarification" in message for message in assistant_messages)
    assert not any('"type"' in message for message in assistant_messages)

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    assert any(task["title"] == "遛狗的日常活动" for task in tasks.json())


def test_assistant_answers_birthday_question_without_mutating_tasks():
    client.headers.pop("X-Session-Token", None)
    _rate_buckets.clear()
    login = client.post(
        "/api/session/login",
        json={
            "display_name": unique_username("assistant-birthday"),
            "password": "assistant-pass",
            "birthday": "1998-03-17",
        },
    )
    assert login.status_code == 200
    client.headers["X-Session-Token"] = login.json()["session_token"]
    ensure_assistant_ready("zh")

    created = client.post("/api/tasks", json={"title": "过生日", "task_kind": "temporary"})
    assert created.status_code == 201

    reply = client.post("/api/assistant/chat", json={"message": "过生日的日期是什么时候？", "lang": "zh"})
    assert reply.status_code == 200
    body = reply.json()

    assistant_messages = [message["content"] for message in body["messages"] if message["role"] == "assistant"]
    assert any("1998-03-17" in message and "下一次生日是" in message for message in assistant_messages)
    assert not any("已更新任务" in message for message in assistant_messages)

    tasks = client.get("/api/tasks?status=all")
    assert tasks.status_code == 200
    birthday_task = next(task for task in tasks.json() if task["title"] == "过生日")
    assert birthday_task["due_date"] is None


def test_assistant_non_question_birthday_statement_becomes_scheduled_task_not_account_reply():
    client.headers.pop("X-Session-Token", None)
    _rate_buckets.clear()
    login = client.post(
        "/api/session/login",
        json={
            "display_name": unique_username("assistant-birthday-statement"),
            "password": "assistant-pass",
            "birthday": "1998-03-24",
        },
    )
    assert login.status_code == 200
    client.headers["X-Session-Token"] = login.json()["session_token"]
    ensure_assistant_ready("zh")

    reply = client.post("/api/assistant/chat", json={"message": "我下周1要过生日", "lang": "zh"})
    assert reply.status_code == 200
    assistant_messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("已添加任务：过生日" in message for message in assistant_messages)
    assert not any("你保存的生日是" in message for message in assistant_messages)

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    created = next(task for task in tasks.json() if task["title"] == "过生日")
    assert created["due_date"] is not None


def test_assistant_other_person_birthday_statement_does_not_hijack_account_birthday():
    client.headers.pop("X-Session-Token", None)
    _rate_buckets.clear()
    login = client.post(
        "/api/session/login",
        json={
            "display_name": unique_username("assistant-other-birthday"),
            "password": "assistant-pass",
            "birthday": "1998-03-24",
        },
    )
    assert login.status_code == 200
    client.headers["X-Session-Token"] = login.json()["session_token"]
    ensure_assistant_ready("zh")

    reply = client.post("/api/assistant/chat", json={"message": "我下周1要给我女朋友过生日", "lang": "zh"})
    assert reply.status_code == 200
    assistant_messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("已添加任务" in message and "女朋友过生日" in message for message in assistant_messages)
    assert not any("你保存的生日是" in message for message in assistant_messages)


def test_assistant_followup_uses_previous_day_context_for_agenda_question():
    client.headers.pop("X-Session-Token", None)
    _rate_buckets.clear()
    login = client.post(
        "/api/session/login",
        json={
            "display_name": unique_username("assistant-day-followup"),
            "password": "assistant-pass",
            "birthday": "1998-03-24",
        },
    )
    assert login.status_code == 200
    client.headers["X-Session-Token"] = login.json()["session_token"]
    ensure_assistant_ready("zh")

    same_day = next_weekday_iso(0)
    prep = client.post("/api/tasks", json={"title": "订蛋糕", "task_kind": "temporary", "due_date": same_day})
    assert prep.status_code == 201

    first = client.post("/api/assistant/chat", json={"message": "我下周1要给我女朋友过生日", "lang": "zh"})
    assert first.status_code == 200

    second = client.post("/api/assistant/chat", json={"message": "那天我有什么安排", "lang": "zh"})
    assert second.status_code == 200
    assistant_messages = [message["content"] for message in second.json()["messages"] if message["role"] == "assistant"]
    assert any("那天" in message and "订蛋糕" in message and "女朋友过生日" in message for message in assistant_messages)


def test_assistant_followup_birthday_statement_strips_discourse_filler_from_title():
    client.headers.pop("X-Session-Token", None)
    _rate_buckets.clear()
    login = client.post(
        "/api/session/login",
        json={
            "display_name": unique_username("assistant-birthday-filler"),
            "password": "assistant-pass",
            "birthday": "1998-03-24",
        },
    )
    assert login.status_code == 200
    client.headers["X-Session-Token"] = login.json()["session_token"]
    ensure_assistant_ready("zh")

    reply = client.post("/api/assistant/chat", json={"message": "那我女朋友下周1过生日", "lang": "zh"})
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    titles = [task["title"] for task in tasks.json()]
    assert any("女朋友过生日" in title for title in titles)
    assert "那我女朋友下周1过生日" not in titles
    assert not any("下周1" in title for title in titles)


def test_assistant_question_clears_pending_followup_instead_of_hijacking_chat():
    client.headers.pop("X-Session-Token", None)
    _rate_buckets.clear()
    login = client.post(
        "/api/session/login",
        json={
            "display_name": unique_username("assistant-birthday-pending"),
            "password": "assistant-pass",
            "birthday": "1998-03-17",
        },
    )
    assert login.status_code == 200
    client.headers["X-Session-Token"] = login.json()["session_token"]
    ensure_assistant_ready("zh")

    client.post("/api/tasks", json={"title": "过生日", "task_kind": "temporary"})

    first = client.post("/api/assistant/chat", json={"message": "删掉不存在的任务", "lang": "zh"})
    assert first.status_code == 200
    assert first.json()["pending"]["type"] == "llm_followup"

    second = client.post("/api/assistant/chat", json={"message": "过生日的日期是什么时候？", "lang": "zh"})
    assert second.status_code == 200
    body = second.json()
    assistant_messages = [message["content"] for message in body["messages"] if message["role"] == "assistant"]
    assert any("1998-03-17" in message and "下一次生日是" in message for message in assistant_messages)
    assert body["pending"]["type"] == ""


def test_assistant_new_daily_statement_clears_pending_followup_and_creates_task():
    login_as(unique_username("assistant-daily-pending"), "assistant-pass")
    ensure_assistant_ready("zh")

    first = client.post("/api/assistant/chat", json={"message": "删掉不存在的任务", "lang": "zh"})
    assert first.status_code == 200
    assert first.json()["pending"]["type"] == "llm_followup"

    second = client.post("/api/assistant/chat", json={"message": "我每天都要做饭", "lang": "zh"})
    assert second.status_code == 200
    assistant_messages = [message["content"] for message in second.json()["messages"] if message["role"] == "assistant"]
    assert any("已添加任务：做饭" in message for message in assistant_messages)
    assert second.json()["pending"]["type"] == ""

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    created = next(task for task in tasks.json() if task["title"] == "做饭")
    assert created["task_kind"] == "daily"


def test_assistant_new_english_daily_statement_clears_pending_followup_and_creates_task():
    login_as(unique_username("assistant-daily-pending-en"), "assistant-pass")
    ensure_assistant_ready("en")

    first = client.post("/api/assistant/chat", json={"message": "delete a task that does not exist", "lang": "en"})
    assert first.status_code == 200
    assert first.json()["pending"]["type"] == "llm_followup"

    second = client.post("/api/assistant/chat", json={"message": "I cook every day", "lang": "en"})
    assert second.status_code == 200
    assistant_messages = [message["content"] for message in second.json()["messages"] if message["role"] == "assistant"]
    assert any("Added task: cook" in message for message in assistant_messages)
    assert second.json()["pending"]["type"] == ""

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    created = next(task for task in tasks.json() if task["title"] == "cook")
    assert created["task_kind"] == "daily"


def test_assistant_answers_existing_task_date_question_without_mutating_it():
    login_as(unique_username("assistant-task-date"), "assistant-pass")
    ensure_assistant_ready("zh")

    created = client.post(
        "/api/tasks",
        json={"title": "date", "task_kind": "temporary", "due_date": "2026-03-25"},
    )
    assert created.status_code == 201

    reply = client.post("/api/assistant/chat", json={"message": "date是什么日期", "lang": "zh"})
    assert reply.status_code == 200
    body = reply.json()

    assistant_messages = [message["content"] for message in body["messages"] if message["role"] == "assistant"]
    assert any("date" in message and "2026-03-25" in message for message in assistant_messages)
    assert body["pending"]["type"] == ""

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    matching = [task for task in tasks.json() if task["title"] == "date"]
    assert len(matching) == 1
    assert matching[0]["due_date"] == "2026-03-25"


def test_assistant_with_api_key_prefers_llm_for_natural_language_task_creation(monkeypatch):
    login_as(unique_username("assistant-llm-natural"), "assistant-pass")
    ensure_assistant_ready("zh")

    monkeypatch.setattr(
        "core.llm.get_runtime_config",
        lambda: {"provider": "deepseek", "api_key": "fake-key", "model": "deepseek-chat"},
    )

    def fake_call(self, system, user, max_tokens=1024):
        assert "下下周三有个date" in user
        return json.dumps(
            {
                "reply": "",
                "requires_clarification": False,
                "clarification_question": "",
                "actions": [
                    {
                        "type": "add_task",
                        "title": "date",
                        "description": "",
                        "priority": 0,
                        "due_date": "2026-03-25",
                    }
                ],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        "core.llm.deepseek_provider.DeepSeekLLMService._call_deepseek",
        fake_call,
    )

    reply = client.post("/api/assistant/chat", json={"message": "下下周三有个date", "lang": "zh"})
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    rows = tasks.json()
    created = next(task for task in rows if task["title"] == "date")
    assert created["due_date"] == "2026-03-25"
    assert not any(task["title"] == "会" for task in rows)


def test_assistant_with_api_key_scopes_weekday_question_to_matching_tasks(monkeypatch):
    login_as(unique_username("assistant-llm-weekday-scope"), "assistant-pass")
    ensure_assistant_ready("zh")

    tuesday = client.post(
        "/api/tasks",
        json={"title": "去打工", "task_kind": "weekly", "recurrence_weekday": 1},
    )
    assert tuesday.status_code == 201
    wednesday = client.post(
        "/api/tasks",
        json={"title": "meeting", "task_kind": "weekly", "recurrence_weekday": 2},
    )
    assert wednesday.status_code == 201

    monkeypatch.setattr(
        "core.llm.get_runtime_config",
        lambda: {"provider": "deepseek", "api_key": "fake-key", "model": "deepseek-chat"},
    )

    def fake_call(self, system, user, max_tokens=1024):
        assert "User message:\n我每周四有哪些任务" in user
        assert "Resolved agenda focus for this request:" in user
        assert "Scope: 每周四" in user
        assert "- (none)" in user
        return json.dumps(
            {
                "reply": "每周四目前还没有挂上的安排。",
                "requires_clarification": False,
                "clarification_question": "",
                "actions": [],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        "core.llm.deepseek_provider.DeepSeekLLMService._call_deepseek",
        fake_call,
    )

    reply = client.post("/api/assistant/chat", json={"message": "我每周四有哪些任务", "lang": "zh"})
    assert reply.status_code == 200
    assistant_messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("每周四目前还没有挂上的安排" in message for message in assistant_messages)
    assert not any("去打工" in message or "meeting" in message for message in assistant_messages)


def test_assistant_answers_weekday_agenda_question_without_creating_fake_task():
    login_as(unique_username("assistant-weekday-agenda"), "assistant-pass")
    ensure_assistant_ready("zh")

    created = client.post(
        "/api/tasks",
        json={"title": "去打工", "task_kind": "weekly", "recurrence_weekday": 1},
    )
    assert created.status_code == 201

    reply = client.post("/api/assistant/chat", json={"message": "我每周二都需要干嘛", "lang": "zh"})
    assert reply.status_code == 200
    body = reply.json()

    assistant_messages = [message["content"] for message in body["messages"] if message["role"] == "assistant"]
    assert any("每周二" in message and "去打工" in message for message in assistant_messages)
    assert not any("已添加任务" in message for message in assistant_messages)

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    rows = tasks.json()
    assert len([task for task in rows if task["title"] == "去打工"]) == 1
    assert not any(task["title"] == "都需要干嘛" for task in rows)


def test_assistant_answers_weekly_plan_question_variant_without_creating_fake_task():
    login_as(unique_username("assistant-weekly-plan-variant"), "assistant-pass")
    ensure_assistant_ready("zh")

    created = client.post(
        "/api/tasks",
        json={"title": "去打工", "task_kind": "weekly", "recurrence_weekday": 1},
    )
    assert created.status_code == 201

    reply = client.post("/api/assistant/chat", json={"message": "我每周二的计划是哪些", "lang": "zh"})
    assert reply.status_code == 200
    body = reply.json()

    assistant_messages = [message["content"] for message in body["messages"] if message["role"] == "assistant"]
    assert any("每周二" in message and "去打工" in message for message in assistant_messages)
    assert not any("已添加任务" in message for message in assistant_messages)

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    rows = tasks.json()
    assert len([task for task in rows if task["title"] == "去打工"]) == 1
    assert not any(task["title"] == "的计划是哪些" for task in rows)


def test_assistant_answers_specific_tuesday_task_query_instead_of_listing_everything():
    login_as(unique_username("assistant-specific-weekday-query"), "assistant-pass")
    ensure_assistant_ready("zh")

    work = client.post(
        "/api/tasks",
        json={"title": "去打工", "task_kind": "weekly", "recurrence_weekday": 1},
    )
    assert work.status_code == 201
    meeting = client.post(
        "/api/tasks",
        json={"title": "meeting", "task_kind": "weekly", "recurrence_weekday": 2},
    )
    assert meeting.status_code == 201
    game = client.post(
        "/api/tasks",
        json={"title": "打游戏", "task_kind": "temporary", "due_date": "2026-03-27"},
    )
    assert game.status_code == 201

    reply = client.post("/api/assistant/chat", json={"message": "我这周二有哪些任务", "lang": "zh"})
    assert reply.status_code == 200
    assistant_messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("这周二" in message and "去打工" in message for message in assistant_messages)
    assert not any("meeting" in message for message in assistant_messages)
    assert not any("打游戏" in message for message in assistant_messages)


def test_assistant_followup_understands_relative_weekday_reference():
    login_as(unique_username("assistant-followup-weekday-query"), "assistant-pass")
    ensure_assistant_ready("zh")

    work = client.post(
        "/api/tasks",
        json={"title": "去打工", "task_kind": "weekly", "recurrence_weekday": 1},
    )
    assert work.status_code == 201
    movie = client.post(
        "/api/tasks",
        json={"title": "看电影", "task_kind": "temporary", "due_date": next_weekday_iso(1)},
    )
    assert movie.status_code == 201

    first = client.post("/api/assistant/chat", json={"message": "我这周二有哪些任务", "lang": "zh"})
    assert first.status_code == 200

    second = client.post("/api/assistant/chat", json={"message": "那下周二呢", "lang": "zh"})
    assert second.status_code == 200
    assistant_messages = [message["content"] for message in second.json()["messages"] if message["role"] == "assistant"]
    assert any("下周二" in message and "去打工" in message and "看电影" in message for message in assistant_messages)


def test_assistant_followup_understands_more_colloquial_agenda_references():
    login_as(unique_username("assistant-colloquial-followups"), "assistant-pass")
    ensure_assistant_ready("zh")

    tuesday = client.post(
        "/api/tasks",
        json={"title": "去打工", "task_kind": "weekly", "recurrence_weekday": 1},
    )
    assert tuesday.status_code == 201
    wednesday = client.post(
        "/api/tasks",
        json={"title": "meeting", "task_kind": "weekly", "recurrence_weekday": 2},
    )
    assert wednesday.status_code == 201
    tomorrow = client.post(
        "/api/tasks",
        json={"title": "交作业", "task_kind": "temporary", "due_date": local_date_offset_iso(1)},
    )
    assert tomorrow.status_code == 201

    first = client.post("/api/assistant/chat", json={"message": "我这周二有哪些任务", "lang": "zh"})
    assert first.status_code == 200

    second = client.post("/api/assistant/chat", json={"message": "那周三呢", "lang": "zh"})
    assert second.status_code == 200
    second_messages = [message["content"] for message in second.json()["messages"] if message["role"] == "assistant"]
    assert any("周三" in message and "meeting" in message for message in second_messages)

    third = client.post("/api/assistant/chat", json={"message": "那每周二呢", "lang": "zh"})
    assert third.status_code == 200
    third_messages = [message["content"] for message in third.json()["messages"] if message["role"] == "assistant"]
    assert any("每周二" in message and "去打工" in message for message in third_messages)

    fourth = client.post("/api/assistant/chat", json={"message": "那明天呢", "lang": "zh"})
    assert fourth.status_code == 200
    fourth_messages = [message["content"] for message in fourth.json()["messages"] if message["role"] == "assistant"]
    assert any("明天" in message and "交作业" in message for message in fourth_messages)


def test_assistant_handles_realistic_weekday_question_sequence_without_creating_junk_tasks():
    login_as(unique_username("assistant-sequence"), "assistant-pass")
    ensure_assistant_ready("zh")

    work = client.post(
        "/api/tasks",
        json={"title": "每周二要去打工", "task_kind": "weekly", "recurrence_weekday": 1},
    )
    assert work.status_code == 201
    meeting = client.post(
        "/api/tasks",
        json={"title": "每周三有meeting", "task_kind": "weekly", "recurrence_weekday": 2},
    )
    assert meeting.status_code == 201

    q1 = client.post("/api/assistant/chat", json={"message": "我这周二有哪些任务", "lang": "zh"})
    assert q1.status_code == 200
    q2 = client.post("/api/assistant/chat", json={"message": "我每周二都需要干嘛", "lang": "zh"})
    assert q2.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    titles = [task["title"] for task in tasks.json()]
    assert "每周二要去打工" in titles
    assert "每周三有meeting" in titles
    assert "我这周二有哪些任务" not in titles
    assert "我每周二都需要干嘛" not in titles
    assert "都需要干嘛" not in titles


def test_assistant_list_reply_filters_out_old_junk_titles():
    login_as(unique_username("assistant-list-filters-junk"), "assistant-pass")
    ensure_assistant_ready("zh")

    client.post("/api/tasks", json={"title": "每周二要去打工", "task_kind": "weekly", "recurrence_weekday": 1})
    client.post("/api/tasks", json={"title": "Clarification: 我每周二都需要干嘛", "task_kind": "temporary"})
    client.post("/api/tasks", json={"title": "都需要干嘛", "task_kind": "temporary"})

    reply = client.post("/api/assistant/chat", json={"message": "我现在有哪些任务", "lang": "zh"})
    assert reply.status_code == 200
    assistant_messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("每周二要去打工" in message for message in assistant_messages)
    assert not any("Clarification:" in message for message in assistant_messages)
    assert not any("都需要干嘛" in message for message in assistant_messages)


def test_assistant_fresh_question_clears_add_task_followup_without_creating_clarification_title():
    login_as(unique_username("assistant-followup-clean"), "assistant-pass")
    ensure_assistant_ready("zh")

    existing = client.post(
        "/api/tasks",
        json={"title": "去打工", "task_kind": "weekly", "recurrence_weekday": 1},
    )
    assert existing.status_code == 201

    first = client.post("/api/assistant/chat", json={"message": "帮我添加任务", "lang": "zh"})
    assert first.status_code == 200
    assert first.json()["pending"]["type"] == "llm_followup"

    second = client.post("/api/assistant/chat", json={"message": "我每周二都需要干嘛", "lang": "zh"})
    assert second.status_code == 200
    body = second.json()
    assistant_messages = [message["content"] for message in body["messages"] if message["role"] == "assistant"]
    assert any("每周二" in message and "去打工" in message for message in assistant_messages)
    assert body["pending"]["type"] == ""

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    rows = tasks.json()
    assert not any(task["title"] == "Clarification: 我每周二都需要干嘛" for task in rows)
    assert not any(task["title"] == "我每周二都需要干嘛" for task in rows if task["title"] != "去打工")


def test_assistant_refuses_least_important_delete_request():
    login_as(unique_username("assistant-no-triage"), "assistant-pass")
    ensure_assistant_ready("zh")

    reply = client.post("/api/assistant/chat", json={"message": "把今天计划里最不重要的任务删掉", "lang": "zh"})
    assert reply.status_code == 200
    body = reply.json()
    assistant_messages = [message["content"] for message in body["messages"] if message["role"] == "assistant"]
    assert any("不替你判断" in message and "最没用" in message or "最不重要" in message for message in assistant_messages)


def test_assistant_defer_moves_task_to_tomorrow():
    login_as(unique_username("assistant-defer"), "assistant-pass")
    ensure_assistant_ready("zh")

    task = client.post("/api/tasks", json={"title": "exam", "task_kind": "temporary"})
    assert task.status_code == 201

    reply = client.post("/api/assistant/chat", json={"message": "把 exam 推迟", "lang": "zh"})
    assert reply.status_code == 200
    assistant_messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("已延后任务：exam" in message for message in assistant_messages)

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    updated = next(item for item in tasks.json() if item["title"] == "exam")
    assert updated["due_date"] == local_date_offset_iso(1)


def test_assistant_defer_handles_day_after_tomorrow_and_semantic_task_name():
    login_as(unique_username("assistant-defer-after-tomorrow"), "assistant-pass")
    ensure_assistant_ready("zh")

    task = client.post("/api/tasks", json={"title": "eat lunch", "task_kind": "temporary"})
    assert task.status_code == 201

    reply = client.post("/api/assistant/chat", json={"message": "帮我把吃午饭的任务推迟到后天", "lang": "zh"})
    assert reply.status_code == 200
    assistant_messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("已延后任务：eat lunch" in message for message in assistant_messages)

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    updated = next(item for item in tasks.json() if item["title"] == "eat lunch")
    assert updated["due_date"] == local_date_offset_iso(2)


def test_assistant_defer_handles_common_ba_typo_prefix():
    login_as(unique_username("assistant-defer-ba"), "assistant-pass")
    ensure_assistant_ready("zh")

    task = client.post("/api/tasks", json={"title": "eat lunch", "task_kind": "temporary"})
    assert task.status_code == 201

    reply = client.post("/api/assistant/chat", json={"message": "帮我吧吃午饭的任务推迟到后天", "lang": "zh"})
    assert reply.status_code == 200
    assistant_messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("已延后任务：eat lunch" in message for message in assistant_messages)


def test_assistant_defer_handles_next_weekday_phrase():
    login_as(unique_username("assistant-defer-next-weekday"), "assistant-pass")
    ensure_assistant_ready("zh")

    task = client.post("/api/tasks", json={"title": "running", "task_kind": "temporary"})
    assert task.status_code == 201

    reply = client.post("/api/assistant/chat", json={"message": "把 running 推迟到下周一", "lang": "zh"})
    assert reply.status_code == 200
    assistant_messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("已延后任务：running" in message for message in assistant_messages)

    tasks = client.get("/api/tasks?status=active")
    assert tasks.status_code == 200
    updated = next(item for item in tasks.json() if item["title"] == "running")
    assert updated["due_date"] is not None


def test_assistant_returns_followup_instead_of_false_success_when_task_missing():
    login_as(unique_username("assistant-missing-followup"), "assistant-pass")
    ensure_assistant_ready("zh")

    reply = client.post("/api/assistant/chat", json={"message": "把不存在的任务推迟到下周一", "lang": "zh"})
    assert reply.status_code == 200
    assistant_messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("更具体" in message or "没定位到" in message for message in assistant_messages)
    assert not any("好的，我已经处理" in message for message in assistant_messages)


def test_assistant_defer_handles_next_month_phrase():
    login_as(unique_username("assistant-defer-next-month"), "assistant-pass")
    ensure_assistant_ready("zh")

    task = client.post("/api/tasks", json={"title": "leetcode", "task_kind": "temporary"})
    assert task.status_code == 201

    reply = client.post("/api/assistant/chat", json={"message": "把 leetcode 推迟到下个月", "lang": "zh"})
    assert reply.status_code == 200
    assistant_messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("已延后任务：leetcode" in message for message in assistant_messages)

    tasks = client.get("/api/tasks?status=active")
    updated = next(item for item in tasks.json() if item["title"] == "leetcode")
    assert updated["due_date"] == next_month_iso()


def test_assistant_defer_handles_weekend_phrase():
    login_as(unique_username("assistant-defer-weekend"), "assistant-pass")
    ensure_assistant_ready("zh")

    task = client.post("/api/tasks", json={"title": "walk dog", "task_kind": "temporary"})
    assert task.status_code == 201

    reply = client.post("/api/assistant/chat", json={"message": "把遛狗推迟到这个周末", "lang": "zh"})
    assert reply.status_code == 200
    assistant_messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("已延后任务：walk dog" in message for message in assistant_messages)

    tasks = client.get("/api/tasks?status=active")
    updated = next(item for item in tasks.json() if item["title"] == "walk dog")
    assert updated["due_date"] == upcoming_weekend_iso()


def test_assistant_defer_handles_tonight_phrase():
    login_as(unique_username("assistant-defer-tonight"), "assistant-pass")
    ensure_assistant_ready("en")

    task = client.post("/api/tasks", json={"title": "buy groceries", "task_kind": "temporary"})
    assert task.status_code == 201

    reply = client.post("/api/assistant/chat", json={"message": "Postpone buy groceries to tonight", "lang": "en"})
    assert reply.status_code == 200
    assistant_messages = [message["content"] for message in reply.json()["messages"] if message["role"] == "assistant"]
    assert any("Deferred task: buy groceries" in message for message in assistant_messages)

    tasks = client.get("/api/tasks?status=active")
    updated = next(item for item in tasks.json() if item["title"] == "buy groceries")
    assert updated["due_date"] == local_date_offset_iso(0)


def test_assistant_update_task_due_date_normalizes_month_day_format():
    login_as(unique_username("assistant-month-day"), "assistant-pass")
    ensure_assistant_ready("zh")

    task = client.post("/api/tasks", json={"title": "完成capstone", "task_kind": "temporary"})
    assert task.status_code == 201

    reply = client.post("/api/assistant/chat", json={"message": "帮我把capstone的ddl设置到3.17", "lang": "zh"})
    assert reply.status_code == 200

    tasks = client.get("/api/tasks?status=active")
    updated = next(item for item in tasks.json() if item["title"] == "完成capstone")
    assert updated["due_date"] == "2026-03-17"


def test_assistant_followup_uses_last_task_reference_for_schedule_question():
    login_as(unique_username("assistant-task-followup-date"), "assistant-pass")
    ensure_assistant_ready("zh")

    task = client.post("/api/tasks", json={"title": "完成capstone", "task_kind": "temporary"})
    assert task.status_code == 201

    first = client.post("/api/assistant/chat", json={"message": "帮我把capstone的ddl设置到3.17", "lang": "zh"})
    assert first.status_code == 200

    second = client.post("/api/assistant/chat", json={"message": "那这个任务是哪天", "lang": "zh"})
    assert second.status_code == 200
    assistant_messages = [message["content"] for message in second.json()["messages"] if message["role"] == "assistant"]
    assert any("完成capstone" in message and "2026-03-17" in message for message in assistant_messages)


def test_review_insights_include_mood_and_focus_signals():
    login_as(unique_username("review-insights"), "assistant-pass")

    task = client.post("/api/tasks", json={"title": "write summary", "task_kind": "temporary"})
    assert task.status_code == 201
    task_id = task.json()["id"]

    mood = client.post("/api/mood", json={"mood_level": 2, "note": "今天状态有点散"})
    assert mood.status_code == 200

    focus = client.post("/api/focus/sessions", json={"task_id": task_id, "duration_minutes": 25, "session_type": "work"})
    assert focus.status_code == 200

    done = client.put(f"/api/tasks/{task_id}", json={"status": "completed"})
    assert done.status_code == 200

    review = client.get(f"/api/review-insights?date={local_date_offset_iso(0)}&month={local_date_offset_iso(0)[:7]}&lang=zh")
    assert review.status_code == 200
    body = review.json()
    assert body["daily"]
    assert body["weekly"]
    assert body["monthly"]
