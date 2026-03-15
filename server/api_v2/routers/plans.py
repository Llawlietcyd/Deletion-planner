from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError

from api_v2.schemas import PlanGenerateRequest
from api_v2.user_context import plan_storage_key, require_current_user
from core.planner import generate_daily_plan, regenerate_reasoning
from core.time import local_today_iso
from database.db import get_db
from database.models import Task, DailyPlan, PlanTask, TaskHistory, TaskStatus, PlanTaskStatus, HistoryAction

router = APIRouter(prefix="/plans", tags=["plans"])


def _visible_plan_tasks(plan: DailyPlan):
    visible = []
    for plan_task in sorted(plan.plan_tasks, key=lambda item: item.order):
        task = plan_task.task
        if not task:
            continue
        if plan_task.status != PlanTaskStatus.PLANNED.value:
            continue
        if task.status != TaskStatus.ACTIVE.value:
            continue
        visible.append(plan_task.to_dict())
    return visible


@router.post("/generate", status_code=201)
def generate_plan(payload: PlanGenerateRequest, request: Request):
    target_date = payload.date or local_today_iso()
    lang = payload.lang
    capacity_units = payload.capacity_units

    with get_db() as db:
        user = require_current_user(db, request)
        storage_key = plan_storage_key(user.id, target_date)
        existing = db.query(DailyPlan).filter(DailyPlan.date == storage_key).first()

        # If force=True, delete existing plan and regenerate from scratch
        if existing and payload.force:
            db.delete(existing)
            db.flush()
            existing = None

        if existing:
            result = existing.to_dict(include_tasks=True)
            result["tasks"] = _visible_plan_tasks(existing)
            active_tasks = db.query(Task).filter(Task.user_id == user.id, Task.status == TaskStatus.ACTIVE.value).all()
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
            .filter(Task.user_id == user.id, Task.status == TaskStatus.ACTIVE.value)
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
            date=storage_key,
            reasoning=plan_result["reasoning"],
            overload_warning=plan_result.get("overload_warning", ""),
            max_tasks=plan_result.get("max_tasks", 4),
        )
        db.add(daily_plan)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            existing = db.query(DailyPlan).filter(DailyPlan.date == storage_key).first()
            if existing:
                result = existing.to_dict(include_tasks=True)
                result["tasks"] = _visible_plan_tasks(existing)
                return result
            raise HTTPException(status_code=409, detail={"error_code": "PLAN_CONFLICT", "message": "Plan was created concurrently"})

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
        result["tasks"] = _visible_plan_tasks(daily_plan)
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
    request: Request,
    lang: str = Query(default="en"),
    capacity_units: Optional[int] = Query(default=None),
):
    today = local_today_iso()
    return get_plan(today, request, lang, capacity_units)


@router.get("/{plan_date}")
def get_plan(
    plan_date: str,
    request: Request,
    lang: str = Query(default="en"),
    capacity_units: Optional[int] = Query(default=None),
):
    with get_db() as db:
        user = require_current_user(db, request)
        storage_key = plan_storage_key(user.id, plan_date)
        plan = db.query(DailyPlan).filter(DailyPlan.date == storage_key).first()
        if not plan:
            raise HTTPException(status_code=404, detail={"error_code": "PLAN_NOT_FOUND", "message": "No plan found for this date"})

        result = plan.to_dict(include_tasks=True)
        result["tasks"] = _visible_plan_tasks(plan)
        active_tasks = db.query(Task).filter(Task.user_id == user.id, Task.status == TaskStatus.ACTIVE.value).all()
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
