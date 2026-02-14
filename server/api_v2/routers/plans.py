from datetime import date
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

    with get_db() as db:
        existing = db.query(DailyPlan).filter(DailyPlan.date == target_date).first()
        if existing:
            result = existing.to_dict(include_tasks=True)
            active_tasks = db.query(Task).filter(Task.status == TaskStatus.ACTIVE.value).all()
            localized = regenerate_reasoning(existing, active_tasks, lang)
            result["reasoning"] = localized["reasoning"]
            result["overload_warning"] = localized["overload_warning"]
            result["deletion_suggestions"] = localized.get("deletion_suggestions", [])
            return result

        active_tasks = (
            db.query(Task)
            .filter(Task.status == TaskStatus.ACTIVE.value)
            .order_by(Task.priority.desc(), Task.created_at)
            .all()
        )
        if not active_tasks:
            raise HTTPException(status_code=400, detail={"error_code": "NO_ACTIVE_TASKS", "message": "No active tasks to plan"})

        plan_result = generate_daily_plan(active_tasks, target_date, lang=lang)
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

        daily_plan = db.query(DailyPlan).get(daily_plan.id)
        result = daily_plan.to_dict(include_tasks=True)
        result["deletion_suggestions"] = plan_result.get("deletion_suggestions", [])
        result["deferred_tasks"] = plan_result.get("deferred_tasks", [])
        return result


@router.get("/today")
def get_today_plan(lang: str = Query(default="en")):
    today = date.today().isoformat()
    return get_plan(today, lang)


@router.get("/{plan_date}")
def get_plan(plan_date: str, lang: str = Query(default="en")):
    with get_db() as db:
        plan = db.query(DailyPlan).filter(DailyPlan.date == plan_date).first()
        if not plan:
            raise HTTPException(status_code=404, detail={"error_code": "PLAN_NOT_FOUND", "message": "No plan found for this date"})

        result = plan.to_dict(include_tasks=True)
        active_tasks = db.query(Task).filter(Task.status == TaskStatus.ACTIVE.value).all()
        localized = regenerate_reasoning(plan, active_tasks, lang)
        result["reasoning"] = localized["reasoning"]
        result["overload_warning"] = localized["overload_warning"]
        result["deletion_suggestions"] = localized.get("deletion_suggestions", [])
        return result
