from datetime import date
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from api_v2.schemas import PlanGenerateRequest
from core.planner import generate_daily_plan, regenerate_reasoning
from database.db import get_db
from database.models import Task, DailyPlan, PlanTask, TaskHistory, TaskStatus, PlanTaskStatus, HistoryAction

router = APIRouter(prefix="/plans", tags=["plans"])


@router.post("/generate", status_code=201)
def generate_plan(payload: PlanGenerateRequest):
    target_date = payload.date or date.today().isoformat()
    lang = payload.lang
    capacity_units = payload.capacity_units

    with get_db() as db:
        existing = db.query(DailyPlan).filter(DailyPlan.date == target_date).first()

        # If force=True, delete existing plan and regenerate from scratch
        if existing and payload.force:
            db.delete(existing)
            db.flush()
            existing = None

        if existing:
            result = existing.to_dict(include_tasks=True)
            active_tasks = db.query(Task).filter(Task.status == TaskStatus.ACTIVE.value).all()
            localized = regenerate_reasoning(
                existing, active_tasks, lang, capacity_units=capacity_units
            )
            result["reasoning"] = localized["reasoning"]
            result["overload_warning"] = localized["overload_warning"]
            result["deletion_suggestions"] = localized.get("deletion_suggestions", [])
            result["capacity_summary"] = localized.get("capacity_summary", {})
            result["decision_summary"] = localized.get("decision_summary", {})
            result["coach_notes"] = localized.get("coach_notes", [])
            result["deferred_tasks"] = localized.get("deferred_tasks", [])
            result["selected_task_ids"] = localized.get("selected_task_ids", [])
            result["deferred_task_ids"] = localized.get("deferred_task_ids", [])
            return result

        active_tasks = (
            db.query(Task)
            .filter(Task.status == TaskStatus.ACTIVE.value)
            .order_by(Task.priority.desc(), Task.created_at)
            .all()
        )
        if not active_tasks:
            raise HTTPException(status_code=400, detail={"error_code": "NO_ACTIVE_TASKS", "message": "No active tasks to plan"})

        plan_result = generate_daily_plan(
            active_tasks, target_date, lang=lang, capacity_units=capacity_units
        )
        category_by_id = {item["task_id"]: item.get("category", "unclassified") for item in plan_result.get("classified_tasks", [])}
        for task in active_tasks:
            if task.id in category_by_id:
                task.category = category_by_id[task.id]
                task.source = "ai"
                task.decision_reason = "Category inferred by planning engine."

        daily_plan = DailyPlan(
            date=target_date,
            reasoning=plan_result["reasoning"],
            overload_warning=plan_result.get("overload_warning", ""),
            max_tasks=plan_result.get("max_tasks", 4),
        )
        db.add(daily_plan)
        db.flush()

        for i, selected in enumerate(plan_result["selected_tasks"]):
            db.add(PlanTask(
                plan_id=daily_plan.id,
                task_id=selected["task_id"],
                status=PlanTaskStatus.PLANNED.value,
                order=i,
            ))
            db.add(TaskHistory(
                task_id=selected["task_id"],
                date=target_date,
                action=HistoryAction.PLANNED.value,
                ai_reasoning=selected.get("reason", ""),
            ))
        db.flush()

        daily_plan = db.get(DailyPlan, daily_plan.id)
        result = daily_plan.to_dict(include_tasks=True)
        result["deletion_suggestions"] = plan_result.get("deletion_suggestions", [])
        result["deferred_tasks"] = plan_result.get("deferred_tasks", [])
        result["capacity_summary"] = plan_result.get("capacity_summary", {})
        result["decision_summary"] = plan_result.get("decision_summary", {})
        result["coach_notes"] = plan_result.get("coach_notes", [])
        result["selected_task_ids"] = plan_result.get("selected_task_ids", [])
        result["deferred_task_ids"] = plan_result.get("deferred_task_ids", [])
        return result


@router.get("/today")
def get_today_plan(
    lang: str = Query(default="en"),
    capacity_units: Optional[int] = Query(default=None),
):
    today = date.today().isoformat()
    return get_plan(today, lang, capacity_units)


@router.get("/{plan_date}")
def get_plan(
    plan_date: str,
    lang: str = Query(default="en"),
    capacity_units: Optional[int] = Query(default=None),
):
    with get_db() as db:
        plan = db.query(DailyPlan).filter(DailyPlan.date == plan_date).first()
        if not plan:
            raise HTTPException(status_code=404, detail={"error_code": "PLAN_NOT_FOUND", "message": "No plan found for this date"})

        result = plan.to_dict(include_tasks=True)
        active_tasks = db.query(Task).filter(Task.status == TaskStatus.ACTIVE.value).all()
        localized = regenerate_reasoning(
            plan, active_tasks, lang, capacity_units=capacity_units
        )
        result["reasoning"] = localized["reasoning"]
        result["overload_warning"] = localized["overload_warning"]
        result["deletion_suggestions"] = localized.get("deletion_suggestions", [])
        result["capacity_summary"] = localized.get("capacity_summary", {})
        result["decision_summary"] = localized.get("decision_summary", {})
        result["coach_notes"] = localized.get("coach_notes", [])
        result["deferred_tasks"] = localized.get("deferred_tasks", [])
        result["selected_task_ids"] = localized.get("selected_task_ids", [])
        result["deferred_task_ids"] = localized.get("deferred_task_ids", [])
        return result
