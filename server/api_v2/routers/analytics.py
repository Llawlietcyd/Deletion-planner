from typing import Optional
import time
from fastapi import APIRouter, Query

from database.db import get_db
from database.models import Task, DailyPlan, PlanTask, TaskHistory, TaskStatus, PlanTaskStatus

router = APIRouter(tags=["analytics"])
_stats_cache = {"expires_at": 0, "payload": None}


@router.get("/history")
def get_history(
    task_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50),
    offset: int = Query(default=0),
):
    with get_db() as db:
        query = db.query(TaskHistory)
        if task_id:
            query = query.filter(TaskHistory.task_id == task_id)
        records = query.order_by(TaskHistory.created_at.desc()).offset(offset).limit(limit).all()
        return [r.to_dict() for r in records]


@router.get("/stats")
def get_stats():
    now = time.time()
    if _stats_cache["payload"] is not None and _stats_cache["expires_at"] > now:
        return _stats_cache["payload"]

    with get_db() as db:
        total_tasks = db.query(Task).count()
        active_tasks = db.query(Task).filter(Task.status == TaskStatus.ACTIVE.value).count()
        completed_tasks = db.query(Task).filter(Task.status == TaskStatus.COMPLETED.value).count()
        deleted_tasks = db.query(Task).filter(Task.status == TaskStatus.DELETED.value).count()
        total_plans = db.query(DailyPlan).count()
        total_plan_tasks = db.query(PlanTask).count()
        completed_plan_tasks = db.query(PlanTask).filter(
            PlanTask.status == PlanTaskStatus.COMPLETED.value
        ).count()
        completion_rate = round(completed_plan_tasks / total_plan_tasks * 100, 1) if total_plan_tasks > 0 else 0
        payload = {
            "total_tasks": total_tasks,
            "active_tasks": active_tasks,
            "completed_tasks": completed_tasks,
            "deleted_tasks": deleted_tasks,
            "total_plans": total_plans,
            "total_plan_tasks": total_plan_tasks,
            "completed_plan_tasks": completed_plan_tasks,
            "completion_rate": completion_rate,
        }
        _stats_cache["payload"] = payload
        _stats_cache["expires_at"] = now + 10
        return payload
