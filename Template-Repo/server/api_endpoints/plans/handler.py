from flask import jsonify, request
from database.db import get_db
from database.models import (
    Task, DailyPlan, PlanTask, TaskHistory,
    TaskStatus, PlanTaskStatus, HistoryAction,
)
from core.planner import generate_daily_plan, regenerate_reasoning
from datetime import date


def GeneratePlanHandler(req):
    """POST /api/plans/generate — generate today's plan using the AI planner."""
    data = req.get_json(silent=True) or {}
    target_date = data.get("date", date.today().isoformat())
    lang = data.get("lang", "en")

    with get_db() as db:
        # Check if plan already exists for this date
        existing = db.query(DailyPlan).filter(DailyPlan.date == target_date).first()
        if existing:
            # Plan exists — regenerate reasoning text in the requested language
            result = existing.to_dict(include_tasks=True)
            active_tasks = (
                db.query(Task)
                .filter(Task.status == TaskStatus.ACTIVE.value)
                .all()
            )
            localized = regenerate_reasoning(existing, active_tasks, lang)
            result["reasoning"] = localized["reasoning"]
            result["overload_warning"] = localized["overload_warning"]
            result["deletion_suggestions"] = localized.get("deletion_suggestions", [])
            return jsonify(result)

        # Get all active tasks
        active_tasks = (
            db.query(Task)
            .filter(Task.status == TaskStatus.ACTIVE.value)
            .order_by(Task.priority.desc(), Task.created_at)
            .all()
        )

        if not active_tasks:
            return jsonify({"error": "No active tasks to plan"}), 400

        # Use the planner engine to generate a plan
        plan_result = generate_daily_plan(active_tasks, target_date, lang=lang)

        # Create the DailyPlan record
        daily_plan = DailyPlan(
            date=target_date,
            reasoning=plan_result["reasoning"],
            overload_warning=plan_result.get("overload_warning", ""),
            max_tasks=plan_result.get("max_tasks", 4),
        )
        db.add(daily_plan)
        db.flush()

        # Create PlanTask records for selected tasks
        for i, selected in enumerate(plan_result["selected_tasks"]):
            pt = PlanTask(
                plan_id=daily_plan.id,
                task_id=selected["task_id"],
                status=PlanTaskStatus.PLANNED.value,
                order=i,
            )
            db.add(pt)

            # Record history
            hist = TaskHistory(
                task_id=selected["task_id"],
                date=target_date,
                action=HistoryAction.PLANNED.value,
                ai_reasoning=selected.get("reason", ""),
            )
            db.add(hist)

        db.flush()

        # Re-query to get full relationships
        daily_plan = db.query(DailyPlan).get(daily_plan.id)
        result = daily_plan.to_dict(include_tasks=True)

        # Attach extra info from planner
        result["deletion_suggestions"] = plan_result.get("deletion_suggestions", [])
        result["deferred_tasks"] = plan_result.get("deferred_tasks", [])

        return jsonify(result), 201


def GetPlanHandler(req, plan_date):
    """GET /api/plans/<date> — get plan for a specific date."""
    lang = req.args.get("lang", "en")

    with get_db() as db:
        plan = db.query(DailyPlan).filter(DailyPlan.date == plan_date).first()
        if not plan:
            return jsonify({"error": "No plan found for this date"}), 404

        result = plan.to_dict(include_tasks=True)
        active_tasks = db.query(Task).filter(Task.status == TaskStatus.ACTIVE.value).all()
        localized = regenerate_reasoning(plan, active_tasks, lang)
        result["reasoning"] = localized["reasoning"]
        result["overload_warning"] = localized["overload_warning"]
        return jsonify(result)


def GetTodayPlanHandler(req):
    """GET /api/plans/today — get today's plan."""
    today = date.today().isoformat()
    lang = req.args.get("lang", "en")

    with get_db() as db:
        plan = db.query(DailyPlan).filter(DailyPlan.date == today).first()
        if not plan:
            return jsonify({"error": "No plan generated for today yet"}), 404

        result = plan.to_dict(include_tasks=True)
        active_tasks = db.query(Task).filter(Task.status == TaskStatus.ACTIVE.value).all()
        localized = regenerate_reasoning(plan, active_tasks, lang)
        result["reasoning"] = localized["reasoning"]
        result["overload_warning"] = localized["overload_warning"]
        return jsonify(result)
