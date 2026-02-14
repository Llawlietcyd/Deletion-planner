import os

os.environ["DATABASE_URL"] = "sqlite:///test_v2.db"

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
