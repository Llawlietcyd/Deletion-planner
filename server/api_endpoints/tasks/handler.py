from flask import jsonify, request
from database.db import get_db
from database.models import Task, TaskHistory, TaskStatus, HistoryAction
from datetime import date


def ListTasksHandler(req):
    """GET /api/tasks — return all active tasks."""
    status_filter = req.args.get("status", "active")

    with get_db() as db:
        query = db.query(Task)
        if status_filter != "all":
            query = query.filter(Task.status == status_filter)
        tasks = query.order_by(Task.priority.desc(), Task.created_at.desc()).all()
        return jsonify([t.to_dict() for t in tasks])


def CreateTaskHandler(req):
    """POST /api/tasks — create a single task."""
    data = req.get_json(force=True)

    if not data or not data.get("title", "").strip():
        return jsonify({"error": "title is required"}), 400

    with get_db() as db:
        task = Task(
            title=data["title"].strip(),
            description=data.get("description", "").strip(),
            priority=data.get("priority", 0),
        )
        db.add(task)
        db.flush()

        # Record history
        history = TaskHistory(
            task_id=task.id,
            date=date.today().isoformat(),
            action=HistoryAction.CREATED.value,
            ai_reasoning="Task created by user.",
        )
        db.add(history)
        db.flush()

        return jsonify(task.to_dict()), 201


def BatchCreateTasksHandler(req):
    """POST /api/tasks/batch — create multiple tasks from free text (one per line)."""
    data = req.get_json(force=True)
    raw_text = data.get("text", "")
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    if not lines:
        return jsonify({"error": "No tasks provided"}), 400

    created = []
    with get_db() as db:
        for line in lines:
            task = Task(title=line)
            db.add(task)
            db.flush()

            history = TaskHistory(
                task_id=task.id,
                date=date.today().isoformat(),
                action=HistoryAction.CREATED.value,
                ai_reasoning="Task created via batch input.",
            )
            db.add(history)
            db.flush()
            created.append(task.to_dict())

    return jsonify(created), 201


def UpdateTaskHandler(req, task_id):
    """PUT /api/tasks/<id> — update a task."""
    data = req.get_json(force=True)

    with get_db() as db:
        task = db.query(Task).get(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404

        if "title" in data:
            task.title = data["title"].strip()
        if "description" in data:
            task.description = data["description"].strip()
        if "priority" in data:
            task.priority = data["priority"]
        if "status" in data:
            task.status = data["status"]

        db.flush()
        return jsonify(task.to_dict())


def DeleteTaskHandler(req, task_id):
    """DELETE /api/tasks/<id> — soft-delete a task."""
    with get_db() as db:
        task = db.query(Task).get(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404

        task.status = TaskStatus.DELETED.value

        history = TaskHistory(
            task_id=task.id,
            date=date.today().isoformat(),
            action=HistoryAction.DELETED.value,
            ai_reasoning="Task deleted by user.",
        )
        db.add(history)
        db.flush()

        return jsonify({"message": "Task deleted", "task": task.to_dict()})
