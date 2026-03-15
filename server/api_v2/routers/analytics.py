from datetime import timedelta
from typing import Optional
import json
import time

from fastapi import APIRouter, Query, Request

from api_v2.user_context import plan_storage_key, require_current_user
from core.time import local_today
from core.llm import get_llm_service
from database.db import get_db
from database.models import DailyPlan, FocusSession, MoodEntry, PlanTask, PlanTaskStatus, Task, TaskHistory, TaskStatus

router = APIRouter(tags=["analytics"])
_stats_cache: dict[int, dict] = {}


def _safe_parse_date(value: str):
    from datetime import date
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


def _review_snapshot(db, user_id: int, start_date, end_date, selected_date_str: str):
    start_key = start_date.isoformat()
    end_key = end_date.isoformat()

    task_history = (
        db.query(TaskHistory)
        .join(Task)
        .filter(Task.user_id == user_id)
        .filter(TaskHistory.date >= start_key, TaskHistory.date <= end_key)
        .order_by(TaskHistory.created_at.asc())
        .all()
    )
    mood_entries = (
        db.query(MoodEntry)
        .filter(MoodEntry.user_id == user_id, MoodEntry.date >= start_key, MoodEntry.date <= end_key)
        .order_by(MoodEntry.created_at.asc())
        .all()
    )
    focus_entries = (
        db.query(FocusSession)
        .filter(FocusSession.user_id == user_id, FocusSession.date >= start_key, FocusSession.date <= end_key)
        .order_by(FocusSession.created_at.asc())
        .all()
    )
    scheduled_tasks = (
        db.query(Task)
        .filter(Task.user_id == user_id, Task.status == TaskStatus.ACTIVE.value)
        .filter(Task.due_date >= start_key, Task.due_date <= end_key)
        .order_by(Task.due_date.asc(), Task.priority.desc(), Task.created_at.asc())
        .all()
    )

    mood_levels = [entry.mood_level for entry in mood_entries if entry.mood_level]
    top_deferred = {}
    for entry in task_history:
        task_title = entry.task.title if entry.task else ""
        if entry.action == "deferred" and task_title:
            top_deferred[task_title] = top_deferred.get(task_title, 0) + 1

    return {
        "start": start_key,
        "end": end_key,
        "selected_date": selected_date_str,
        "created": sum(1 for entry in task_history if entry.action == "created"),
        "completed": sum(1 for entry in task_history if entry.action == "completed"),
        "deferred": sum(1 for entry in task_history if entry.action == "deferred"),
        "deleted": sum(1 for entry in task_history if entry.action == "deleted"),
        "planned": sum(1 for entry in task_history if entry.action == "planned"),
        "focus_sessions": len(focus_entries),
        "focus_minutes": sum(int(entry.duration_minutes or 0) for entry in focus_entries),
        "scheduled_count": len(scheduled_tasks),
        "mood_average": round(sum(mood_levels) / len(mood_levels), 1) if mood_levels else None,
        "mood_entries": len(mood_entries),
        "mood_notes": [entry.note.strip() for entry in mood_entries if (entry.note or "").strip()][:5],
        "top_deferred": sorted(top_deferred.items(), key=lambda item: item[1], reverse=True)[:3],
    }


def _fallback_review_text(snapshot: dict, scope: str, lang: str) -> str:
    scope_label = {
        "daily review": "每日复盘",
        "weekly review": "每周复盘",
        "monthly review": "每月复盘",
    }.get(scope, scope)
    mood_avg = snapshot.get("mood_average")
    notes = snapshot.get("mood_notes") or []
    deferred = snapshot.get("deferred", 0)
    completed = snapshot.get("completed", 0)
    focus_minutes = snapshot.get("focus_minutes", 0)
    scheduled = snapshot.get("scheduled_count", 0)
    top_def = snapshot.get("top_deferred") or []

    if lang == "zh":
        parts = [f"{scope_label}里完成 {completed} 项，推迟 {deferred} 次，专注 {focus_minutes} 分钟，未来安排 {scheduled} 项。"]
        if mood_avg is not None:
            parts.append(f"心情均值约 {mood_avg}/5。")
        if notes:
            parts.append(f"最近的情绪备注里最明显的一条是：{notes[0]}。")
        if top_def:
            parts.append(f"最常被推迟的是 {top_def[0][0]}。")
        if deferred > completed:
            parts.append("这一段更像在不断把事情往后推，先收紧承诺会比继续加压更有效。")
        elif completed > 0:
            parts.append("你已经有稳定执行信号，下一步值得观察哪些任务总能在合适时段被完成。")
        else:
            parts.append("现在样本还偏少，继续记录心情、专注和结果，复盘会更快变得有用。")
        return " ".join(parts)

    parts = [f"In this {scope}, you completed {completed} task(s), deferred {deferred}, logged {focus_minutes} focus minute(s), and scheduled {scheduled} future task(s)."]
    if mood_avg is not None:
        parts.append(f"Average mood was about {mood_avg}/5.")
    if notes:
        parts.append(f"A recent mood note pointed to: {notes[0]}.")
    if top_def:
        parts.append(f"The most repeatedly deferred task was {top_def[0][0]}.")
    if deferred > completed:
        parts.append("The pattern still leans toward pushing tasks forward, so shrinking commitments will likely help more than adding pressure.")
    elif completed > 0:
        parts.append("There is enough execution signal here to notice which tasks close best under real energy.")
    else:
        parts.append("The sample is still thin, so more mood, focus, and outcome logs will make the review much sharper.")
    return " ".join(parts)


def _llm_review_text(snapshot: dict, scope: str, lang: str) -> str:
    llm = get_llm_service(lang=lang)
    if not hasattr(llm, "_call_deepseek") or not getattr(llm, "api_key", ""):
        return _fallback_review_text(snapshot, scope, lang)

    lang_instruction = "Respond in Simplified Chinese." if lang == "zh" else "Respond in English."
    prompt = f"""You are writing a concise review summary for a personal planning app.
Scope: {scope}
Signals:
{json.dumps(snapshot, ensure_ascii=False)}

Write 2-4 sentences.
- Include mood if it exists.
- Mention completion, deferral, and focus patterns.
- Mention one concrete next-step suggestion.
- Sound human, not robotic.
{lang_instruction}
Return plain text only."""
    try:
        return llm._call_deepseek(
            "You write concise behavioral review summaries for a personal planning product.",
            prompt,
            max_tokens=220,
        )
    except Exception:
        return _fallback_review_text(snapshot, scope, lang)


@router.get("/history")
def get_history(
    request: Request,
    task_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50),
    offset: int = Query(default=0),
):
    with get_db() as db:
        user = require_current_user(db, request)
        query = db.query(TaskHistory).join(Task).filter(Task.user_id == user.id)
        if task_id:
            query = query.filter(TaskHistory.task_id == task_id)
        records = query.order_by(TaskHistory.created_at.desc()).offset(offset).limit(limit).all()
        return [record.to_dict() for record in records]


@router.get("/stats")
def get_stats(request: Request):
    with get_db() as db:
        user = require_current_user(db, request)
        now = time.time()
        user_cache = _stats_cache.get(user.id)
        if user_cache and user_cache["expires_at"] > now:
            return user_cache["payload"]
        plan_prefix = f"{user.id}:%"
        total_tasks = db.query(Task).filter(Task.user_id == user.id).count()
        active_tasks = db.query(Task).filter(Task.user_id == user.id, Task.status == TaskStatus.ACTIVE.value).count()
        completed_tasks = db.query(Task).filter(Task.user_id == user.id, Task.status == TaskStatus.COMPLETED.value).count()
        deleted_tasks = db.query(Task).filter(Task.user_id == user.id, Task.status == TaskStatus.DELETED.value).count()
        total_plans = db.query(DailyPlan).filter(DailyPlan.date.like(plan_prefix)).count()
        total_plan_tasks = db.query(PlanTask).join(DailyPlan).filter(DailyPlan.date.like(plan_prefix)).count()
        completed_plan_tasks = db.query(PlanTask).join(DailyPlan).filter(
            DailyPlan.date.like(plan_prefix),
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
        _stats_cache[user.id] = {"payload": payload, "expires_at": now + 10}
        return payload


@router.get("/weekly-summary")
def get_weekly_summary(request: Request, lang: str = Query(default="en")):
    """Generate a weekly summary of task activity."""

    today = local_today()
    week_start = today - timedelta(days=today.weekday())
    week_start_str = week_start.isoformat()
    today_str = today.isoformat()

    with get_db() as db:
        user = require_current_user(db, request)
        entries = (
            db.query(TaskHistory)
            .join(Task)
            .filter(Task.user_id == user.id)
            .filter(TaskHistory.date >= week_start_str, TaskHistory.date <= today_str)
            .all()
        )

        created = sum(1 for entry in entries if entry.action == "created")
        completed = sum(1 for entry in entries if entry.action == "completed")
        deleted = sum(1 for entry in entries if entry.action == "deleted")
        deferred = sum(1 for entry in entries if entry.action == "deferred")
        planned = sum(1 for entry in entries if entry.action == "planned")

        active_count = db.query(Task).filter(Task.user_id == user.id, Task.status == TaskStatus.ACTIVE.value).count()
        plan_keys = [plan_storage_key(user.id, value) for value in (week_start_str, today_str)]
        start_key, end_key = plan_keys
        plans = db.query(DailyPlan).filter(
            DailyPlan.date >= start_key,
            DailyPlan.date <= end_key,
        ).count()

        week_plan_tasks = (
            db.query(PlanTask)
            .join(DailyPlan)
            .filter(DailyPlan.date >= start_key, DailyPlan.date <= end_key)
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


@router.get("/review-insights")
def get_review_insights(
    request: Request,
    date: str = Query(...),
    month: str = Query(default=""),
    lang: str = Query(default="en"),
):
    target_date = _safe_parse_date(date)
    if target_date is None:
        return {"daily": "", "weekly": "", "monthly": ""}

    month_start = _safe_parse_date(f"{month}-01") if month else target_date.replace(day=1)
    if month_start is None:
        month_start = target_date.replace(day=1)

    week_start = target_date - timedelta(days=target_date.weekday())
    week_end = week_start + timedelta(days=6)
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1, day=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1, day=1)
    month_end = next_month - timedelta(days=1)

    with get_db() as db:
        user = require_current_user(db, request)
        daily_snapshot = _review_snapshot(db, user.id, target_date, target_date, target_date.isoformat())
        weekly_snapshot = _review_snapshot(db, user.id, week_start, week_end, target_date.isoformat())
        monthly_snapshot = _review_snapshot(db, user.id, month_start, month_end, target_date.isoformat())
        return {
            "daily": _llm_review_text(daily_snapshot, "daily review", lang),
            "weekly": _llm_review_text(weekly_snapshot, "weekly review", lang),
            "monthly": _llm_review_text(monthly_snapshot, "monthly review", lang),
        }
