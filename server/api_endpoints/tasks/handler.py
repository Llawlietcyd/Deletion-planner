from flask import jsonify, request
from database.db import get_db
from database.models import Task, TaskHistory, TaskStatus, HistoryAction
from datetime import date, datetime, timezone

ALLOWED_CATEGORIES = {"core", "deferrable", "deletion_candidate", "unclassified"}


def _safe_text(value):
    return (value or "").strip()


def ListTasksHandler(req):
    """GET /api/tasks — return all active tasks."""
    status_filter = req.args.get("status", "active")

    with get_db() as db:
        query = db.query(Task)
        if status_filter != "all":
            query = query.filter(Task.status == status_filter)
        tasks = query.order_by(Task.sort_order.asc(), Task.priority.desc(), Task.created_at.desc()).all()
        return jsonify([t.to_dict() for t in tasks])


def CreateTaskHandler(req):
    """POST /api/tasks — create a single task."""
    data = req.get_json(force=True)

    title = _safe_text(data.get("title")) if data else ""
    if not title:
        return jsonify({"error": "title is required"}), 400

    category = data.get("category", "unclassified")
    if category not in ALLOWED_CATEGORIES:
        return jsonify({"error": "invalid category"}), 400

    with get_db() as db:
        task = Task(
            title=title,
            description=_safe_text(data.get("description", "")),
            category=category,
            priority=data.get("priority", 0),
            sort_order=data.get("sort_order", 0),
            source="manual",
            decision_reason="User-created task.",
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
    data = req.get_json(force=True) or {}

    with get_db() as db:
        task = db.query(Task).get(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404

        prev_status = task.status

        if "title" in data:
            title = _safe_text(data["title"])
            if not title:
                return jsonify({"error": "title cannot be empty"}), 400
            task.title = title
        if "description" in data:
            task.description = _safe_text(data["description"])
        if "priority" in data:
            task.priority = data["priority"]
        if "sort_order" in data:
            task.sort_order = int(data["sort_order"])
        if "category" in data:
            category = data["category"]
            if category not in ALLOWED_CATEGORIES:
                return jsonify({"error": "invalid category"}), 400
            task.category = category
        if "status" in data:
            status = data["status"]
            if status not in {
                TaskStatus.ACTIVE.value,
                TaskStatus.COMPLETED.value,
                TaskStatus.DELETED.value,
            }:
                return jsonify({"error": "invalid status"}), 400
            task.status = status
        if "deferral_count_delta" in data:
            delta = int(data.get("deferral_count_delta", 0))
            if delta > 0:
                task.deferral_count += delta
                db.add(TaskHistory(
                    task_id=task.id,
                    date=date.today().isoformat(),
                    action=HistoryAction.DEFERRED.value,
                    ai_reasoning=f"Task deferred (total deferrals: {task.deferral_count}).",
                ))

        # Record status transitions and keep counters in sync.
        if "status" in data and task.status != prev_status:
            if task.status == TaskStatus.COMPLETED.value:
                task.completion_count += 1
                task.completed_at = datetime.now(timezone.utc)
                task.source = "manual"
                task.decision_reason = "Marked as completed by user."
                db.add(TaskHistory(
                    task_id=task.id,
                    date=date.today().isoformat(),
                    action=HistoryAction.COMPLETED.value,
                    ai_reasoning="Task completed by user.",
                ))
            elif task.status == TaskStatus.DELETED.value:
                task.deleted_at = datetime.now(timezone.utc)
                task.source = "manual"
                task.decision_reason = "Deleted by user."
                db.add(TaskHistory(
                    task_id=task.id,
                    date=date.today().isoformat(),
                    action=HistoryAction.DELETED.value,
                    ai_reasoning="Task deleted by user.",
                ))

        db.flush()
        return jsonify(task.to_dict())


def ReorderTasksHandler(req):
    """PUT /api/tasks/reorder — reorder tasks by ordered id list."""
    data = req.get_json(force=True) or {}
    ordered_ids = data.get("ordered_task_ids", [])
    if not isinstance(ordered_ids, list) or not ordered_ids:
        return jsonify({"error": "ordered_task_ids must be a non-empty list"}), 400

    with get_db() as db:
        tasks = db.query(Task).filter(Task.id.in_(ordered_ids)).all()
        task_by_id = {t.id: t for t in tasks}

        for idx, task_id in enumerate(ordered_ids):
            task = task_by_id.get(int(task_id))
            if task:
                task.sort_order = idx
                task.source = "manual"
                task.decision_reason = "Task manually reordered by user."

        db.flush()
        return jsonify({"message": "Tasks reordered", "count": len(ordered_ids)})


def DeleteTaskHandler(req, task_id):
    """DELETE /api/tasks/<id> — soft-delete a task."""
    hard_delete = req.args.get("hard", "false").lower() == "true"

    with get_db() as db:
        task = db.query(Task).get(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404

        # Allow permanent deletion for already deleted tasks (or explicit hard delete).
        if hard_delete or task.status == TaskStatus.DELETED.value:
            db.delete(task)
            db.flush()
            return jsonify({"message": "Task permanently deleted", "task_id": task_id})

        task.status = TaskStatus.DELETED.value
        task.deleted_at = datetime.now(timezone.utc)
        task.source = "manual"
        task.decision_reason = "Deleted by user."

        history = TaskHistory(
            task_id=task.id,
            date=date.today().isoformat(),
            action=HistoryAction.DELETED.value,
            ai_reasoning="Task deleted by user.",
        )
        db.add(history)
        db.flush()

        return jsonify({"message": "Task deleted", "task": task.to_dict()})
