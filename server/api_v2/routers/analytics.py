from datetime import date, timedelta
from typing import Optional
import time

from fastapi import APIRouter, Query

from database.db import get_db
from database.models import DailyPlan, PlanTask, PlanTaskStatus, Task, TaskHistory, TaskStatus

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
        return [record.to_dict() for record in records]


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
        completion_rate = (
            round(completed_plan_tasks / total_plan_tasks * 100, 1)
            if total_plan_tasks > 0
            else 0
        )
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


@router.get("/weekly-summary")
def get_weekly_summary(lang: str = Query(default="en")):
    """Generate a weekly summary of task activity."""

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_start_str = week_start.isoformat()
    today_str = today.isoformat()

    with get_db() as db:
        entries = (
            db.query(TaskHistory)
            .filter(TaskHistory.date >= week_start_str, TaskHistory.date <= today_str)
            .all()
        )

        created = sum(1 for entry in entries if entry.action == "created")
        completed = sum(1 for entry in entries if entry.action == "completed")
        deleted = sum(1 for entry in entries if entry.action == "deleted")
        deferred = sum(1 for entry in entries if entry.action == "deferred")
        planned = sum(1 for entry in entries if entry.action == "planned")

        active_count = db.query(Task).filter(Task.status == TaskStatus.ACTIVE.value).count()
        plans = db.query(DailyPlan).filter(
            DailyPlan.date >= week_start_str,
            DailyPlan.date <= today_str,
        ).count()

        week_plan_tasks = (
            db.query(PlanTask)
            .join(DailyPlan)
            .filter(DailyPlan.date >= week_start_str, DailyPlan.date <= today_str)
            .all()
        )
        week_completed_plan = sum(
            1 for plan_task in week_plan_tasks if plan_task.status == PlanTaskStatus.COMPLETED.value
        )
        week_total_plan = len(week_plan_tasks)
        week_rate = round(week_completed_plan / week_total_plan * 100, 1) if week_total_plan > 0 else 0

    if lang == "zh":
        summary = (
            f"本周总结（{week_start_str} 到 {today_str}）：\n"
            f"- 新建任务：{created} 项\n"
            f"- 完成任务：{completed} 项\n"
            f"- 删除任务：{deleted} 项\n"
            f"- 推迟任务：{deferred} 次\n"
            f"- 生成计划：{plans} 次\n"
            f"- 计划完成率：{week_rate}%（{week_completed_plan}/{week_total_plan}）\n"
            f"- 当前活跃任务：{active_count} 项"
        )
        if deferred > completed:
            summary += "\n\n本周推迟次数多于完成次数，建议重新审视优先级，并删除低价值任务。"
        elif completed > 0:
            summary += "\n\n本周执行表现不错，继续把注意力留给核心任务。"
    else:
        summary = (
            f"Weekly Summary ({week_start_str} to {today_str}):\n"
            f"- Tasks created: {created}\n"
            f"- Tasks completed: {completed}\n"
            f"- Tasks deleted: {deleted}\n"
            f"- Tasks deferred: {deferred}\n"
            f"- Plans generated: {plans}\n"
            f"- Plan completion rate: {week_rate}% ({week_completed_plan}/{week_total_plan})\n"
            f"- Active tasks remaining: {active_count}"
        )
        if deferred > completed:
            summary += "\n\nMore deferrals than completions this week. Consider reviewing priorities and deleting low-value tasks."
        elif completed > 0:
            summary += "\n\nGood progress. Keep focusing on core tasks."

    return {
        "week_start": week_start_str,
        "week_end": today_str,
        "created": created,
        "completed": completed,
        "deleted": deleted,
        "deferred": deferred,
        "planned": planned,
        "plans": plans,
        "active_tasks": active_count,
        "completion_rate": week_rate,
        "summary": summary,
    }
