from flask import jsonify
from database.db import get_db
from database.models import (
    Task, DailyPlan, PlanTask, TaskHistory,
    TaskStatus, PlanTaskStatus, HistoryAction,
)
from core.deletion import check_deletion_candidates
from datetime import date


def SubmitFeedbackHandler(req):
    """POST /api/feedback — submit completion feedback for today's plan.

    Expected body:
    {
        "date": "2026-02-13",        // optional, defaults to today
        "results": [
            {"plan_task_id": 1, "status": "completed"},
            {"plan_task_id": 2, "status": "missed"},
            ...
        ]
    }
    """
    data = req.get_json(force=True)
    target_date = data.get("date", date.today().isoformat())
    results = data.get("results", [])
    lang = data.get("lang", "en")

    if not results:
        return jsonify({"error": "No feedback results provided"}), 400

    deletion_suggestions = []

    with get_db() as db:
        plan = db.query(DailyPlan).filter(DailyPlan.date == target_date).first()
        if not plan:
            return jsonify({"error": "No plan found for this date"}), 404

        for entry in results:
            pt = db.query(PlanTask).get(entry["plan_task_id"])
            if not pt or pt.plan_id != plan.id:
                continue

            new_status = entry["status"]
            pt.status = new_status

            task = db.query(Task).get(pt.task_id)
            if not task:
                continue

            # Update task counters
            if new_status == PlanTaskStatus.COMPLETED.value:
                task.completion_count += 1
                task.status = TaskStatus.COMPLETED.value
                action = HistoryAction.COMPLETED.value
                reasoning = "Task completed by user."
            elif new_status == PlanTaskStatus.MISSED.value:
                action = HistoryAction.MISSED.value
                reasoning = "Task was planned but not completed."
            elif new_status == PlanTaskStatus.DEFERRED.value:
                task.deferral_count += 1
                action = HistoryAction.DEFERRED.value
                reasoning = f"Task deferred (total deferrals: {task.deferral_count})."
            else:
                continue

            hist = TaskHistory(
                task_id=task.id,
                date=target_date,
                action=action,
                ai_reasoning=reasoning,
            )
            db.add(hist)

        db.flush()

        # Check for deletion candidates after processing feedback
        active_tasks = (
            db.query(Task)
            .filter(Task.status == TaskStatus.ACTIVE.value)
            .all()
        )
        deletion_suggestions = check_deletion_candidates(active_tasks, lang=lang)

    return jsonify({
        "message": "Feedback recorded",
        "deletion_suggestions": deletion_suggestions,
    })


def GetHistoryHandler(req):
    """GET /api/history — get task history with optional filters."""
    task_id = req.args.get("task_id")
    limit = int(req.args.get("limit", 50))

    with get_db() as db:
        query = db.query(TaskHistory)
        if task_id:
            query = query.filter(TaskHistory.task_id == int(task_id))
        records = query.order_by(TaskHistory.created_at.desc()).limit(limit).all()
        return jsonify([r.to_dict() for r in records])


def GetStatsHandler(req):
    """GET /api/stats — get summary statistics."""
    with get_db() as db:
        total_tasks = db.query(Task).count()
        active_tasks = db.query(Task).filter(Task.status == TaskStatus.ACTIVE.value).count()
        completed_tasks = db.query(Task).filter(Task.status == TaskStatus.COMPLETED.value).count()
        deleted_tasks = db.query(Task).filter(Task.status == TaskStatus.DELETED.value).count()
        total_plans = db.query(DailyPlan).count()

        # Completion rate from plan tasks
        total_plan_tasks = db.query(PlanTask).count()
        completed_plan_tasks = db.query(PlanTask).filter(
            PlanTask.status == PlanTaskStatus.COMPLETED.value
        ).count()

        completion_rate = (
            round(completed_plan_tasks / total_plan_tasks * 100, 1)
            if total_plan_tasks > 0 else 0
        )

        return jsonify({
            "total_tasks": total_tasks,
            "active_tasks": active_tasks,
            "completed_tasks": completed_tasks,
            "deleted_tasks": deleted_tasks,
            "total_plans": total_plans,
            "total_plan_tasks": total_plan_tasks,
            "completed_plan_tasks": completed_plan_tasks,
            "completion_rate": completion_rate,
        })
