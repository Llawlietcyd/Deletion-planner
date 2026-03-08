import os
import sys

# Ensure server directory is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "sqlite:///test_v2.db"
os.environ["LLM_PROVIDER"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402
from api_v2.main import app  # noqa: E402
from database.db import init_db  # noqa: E402

init_db()
client = TestClient(app)


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_task_lifecycle():
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


def test_search_tasks():
    """Search tasks by keyword."""
    client.post("/api/tasks", json={"title": "Learn Python basics"})
    client.post("/api/tasks", json={"title": "Buy groceries"})

    res = client.get("/api/tasks?status=active&q=Python")
    assert res.status_code == 200
    results = res.json()
    assert any("Python" in t["title"] for t in results)
    assert not any("groceries" in t["title"] for t in results)


def test_batch_create_with_markers():
    """Batch create should parse priority and due date markers."""
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


def test_reorder_tasks():
    t1 = client.post("/api/tasks", json={"title": "Reorder A"}).json()["id"]
    t2 = client.post("/api/tasks", json={"title": "Reorder B"}).json()["id"]
    t3 = client.post("/api/tasks", json={"title": "Reorder C"}).json()["id"]

    res = client.put("/api/tasks/reorder", json={"ordered_task_ids": [t3, t1, t2]})
    assert res.status_code == 200
    assert res.json()["count"] == 3


def test_history_pagination():
    res = client.get("/api/history?limit=5&offset=0")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_weekly_summary():
    res = client.get("/api/weekly-summary?lang=en")
    assert res.status_code == 200
    body = res.json()
    assert "summary" in body
    assert "completion_rate" in body


def test_llm_settings():
    res = client.get("/api/settings/llm")
    assert res.status_code == 200
    assert "provider" in res.json()

    update = client.put("/api/settings/llm", json={"provider": "mock"})
    assert update.status_code == 200
    assert update.json()["provider"] == "mock"

    deepseek = client.put("/api/settings/llm", json={"provider": "deepseek"})
    assert deepseek.status_code == 200
    assert deepseek.json()["provider"] == "deepseek"

    test = client.post("/api/settings/llm/test")
    assert test.status_code == 200
    assert "ok" in test.json()


def test_stats():
    res = client.get("/api/stats")
    assert res.status_code == 200
    body = res.json()
    assert "active_tasks" in body
    assert "completion_rate" in body
