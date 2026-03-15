from datetime import datetime, timezone
import re
from fastapi import APIRouter, HTTPException, Query, Request

from api_v2.user_context import require_current_user
from api_v2.schemas import TaskCreateRequest, TaskUpdateRequest, TaskBatchCreateRequest, ReorderRequest
from core.task_kind import (
    infer_recurrence_weekday,
    infer_task_kind,
    normalize_recurrence_weekday,
    normalize_task_kind,
    strip_task_kind_markers,
)
from core.time import APP_TIMEZONE, local_date_offset_iso, local_today_iso, normalize_date_string
from database.db import get_db
from database.models import Task, TaskHistory, TaskStatus, HistoryAction

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _is_recurring(task: Task) -> bool:
    return (task.task_kind or "temporary") in {"daily", "weekly"}


def _cleanup_concierge_title(title: str) -> str:
    cleaned = (title or "").strip()
    if not cleaned:
        return ""
    patterns = [
        r"^(帮我|给我|请|麻烦你)?\s*(加上一个|加入一个|添加一个|新增一个|加一个|加一项|加一条|加上|加入|添加|新增|加个)\s*",
        r"^(i need to|i have to|i should|i want to)\s+",
        r"^(add|create)\s+((a|an)\s+)?(task:?\s*)?",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(这个|一个|一项|一条)\s*$", "", cleaned)
    cleaned = re.sub(r"(这个)?任务$", "", cleaned)
    cleaned = re.sub(r"的$", "", cleaned)
    cleaned = re.sub(r"[。．.!！]+$", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" ：:，,.")


def _is_junk_concierge_title(title: str) -> bool:
    normalized = (title or "").strip().lower()
    if not normalized:
        return False
    if normalized.startswith("clarification:") or normalized.startswith("additional clarification:"):
        return True
    junk_fragments = (
        "有哪些任务",
        "有什么任务",
        "都需要干嘛",
        "有啥安排",
        "有安排吗",
        "是什么日期",
        "是什么时候",
        "what tasks",
        "what do i have",
        "what date is",
        "what day is",
    )
    if any(fragment in normalized for fragment in junk_fragments):
        return True
    return ("?" in normalized or "？" in normalized) and len(normalized) > 6


@router.get("")
def list_tasks(request: Request, status: str = Query(default="active"), q: str = Query(default="")):
    with get_db() as db:
        user = require_current_user(db, request)
        query = db.query(Task).filter(Task.user_id == user.id)
        if status != "all":
            query = query.filter(Task.status == status)
        if q.strip():
            keyword = f"%{q.strip()}%"
            query = query.filter(
                (Task.title.ilike(keyword)) | (Task.description.ilike(keyword))
            )
        tasks = query.order_by(Task.sort_order.asc(), Task.priority.desc(), Task.created_at.desc()).all()
        changed = False
        for task in tasks:
            if task.decision_reason == "Created by concierge.":
                cleaned = _cleanup_concierge_title(task.title)
                if cleaned and cleaned != task.title:
                    task.title = cleaned
                    changed = True
            inferred_weekday = infer_recurrence_weekday(task.title, task.description, task.recurrence_weekday)
            inferred_kind = infer_task_kind(task.title, task.description, task.due_date, None)
            if (
                task.task_kind == "temporary"
                and not task.due_date
                and task.source == "ai"
                and task.category == "core"
                and task.decision_reason == "Category inferred during onboarding."
                and inferred_kind == "temporary"
            ):
                inferred_kind = "daily"
            if task.task_kind == "daily" and inferred_kind == "temporary":
                inferred_kind = "daily"
            if task.task_kind == "weekly" and inferred_kind == "temporary":
                inferred_kind = "weekly"
            if inferred_kind != task.task_kind:
                task.task_kind = inferred_kind
                changed = True
            normalized_weekday = inferred_weekday if task.task_kind == "weekly" else None
            if normalized_weekday != task.recurrence_weekday:
                task.recurrence_weekday = normalized_weekday
                changed = True
            normalized_due_date = normalize_date_string(task.due_date)
            if normalized_due_date != task.due_date:
                task.due_date = normalized_due_date
                changed = True
        if changed:
            db.flush()
        visible_tasks = [
            task for task in tasks
            if not (task.decision_reason == "Created by concierge." and _is_junk_concierge_title(task.title))
        ]
        return [t.to_dict() for t in visible_tasks]


@router.post("", status_code=201)
def create_task(payload: TaskCreateRequest, request: Request):
    with get_db() as db:
        user = require_current_user(db, request)
        clean_title, marker_kind = strip_task_kind_markers(payload.title)
        task_kind = infer_task_kind(clean_title, payload.description, payload.due_date, payload.task_kind or marker_kind)
        recurrence_weekday = infer_recurrence_weekday(clean_title, payload.description, payload.recurrence_weekday)
        due_date = normalize_date_string(payload.due_date)
        task = Task(
            user_id=user.id,
            title=clean_title.strip(),
            description=payload.description.strip(),
            priority=payload.priority,
            sort_order=payload.sort_order,
            category=payload.category,
            due_date=due_date,
            source="manual",
            task_kind=task_kind,
            recurrence_weekday=recurrence_weekday if task_kind == "weekly" else None,
            decision_reason="User-created task.",
        )
        db.add(task)
        db.flush()

        db.add(TaskHistory(
            task_id=task.id,
            date=local_today_iso(),
            action=HistoryAction.CREATED.value,
            ai_reasoning="Task created by user.",
        ))
        db.flush()
        return task.to_dict()


@router.post("/batch", status_code=201)
def batch_create_tasks(payload: TaskBatchCreateRequest, request: Request):
    lines = [line.strip() for line in payload.text.splitlines() if line.strip()]
    if not lines:
        raise HTTPException(status_code=400, detail={"error_code": "INVALID_BATCH", "message": "No tasks provided"})

    created = []
    with get_db() as db:
        user = require_current_user(db, request)
        for line in lines:
            title, priority, due_date, explicit_kind = _parse_task_line(line)
            task_kind = infer_task_kind(title, "", due_date, explicit_kind)
            task = Task(
                user_id=user.id,
                title=title,
                priority=priority,
                due_date=due_date,
                task_kind=task_kind,
                recurrence_weekday=infer_recurrence_weekday(title) if task_kind == "weekly" else None,
            )
            db.add(task)
            db.flush()
            db.add(TaskHistory(
                task_id=task.id,
                date=local_today_iso(),
                action=HistoryAction.CREATED.value,
                ai_reasoning="Task created via batch input.",
            ))
            db.flush()
            created.append(task.to_dict())
    return created


def _parse_task_line(line: str):
    """Parse a task line with optional inline markers.
    
    Supports:
      - Priority: !low !medium !high !urgent or !低 !中 !高 !紧急
      - Due date: @2025-03-15 or @tomorrow or @today
    """
    import re
    priority = 0
    due_date = None
    explicit_kind = None
    text, marker_kind = strip_task_kind_markers(line)
    if marker_kind:
        explicit_kind = marker_kind

    # Priority markers
    priority_map = {
        '!urgent': 5, '!紧急': 5,
        '!high': 3, '!高': 3,
        '!medium': 1, '!中': 1,
        '!low': 0, '!低': 0,
    }
    for marker, prio in priority_map.items():
        if marker in text.lower():
            priority = prio
            text = re.sub(re.escape(marker), '', text, flags=re.IGNORECASE).strip()
            break

    # Due date markers
    date_match = re.search(r'@(\d{4}-\d{2}-\d{2})', text)
    if date_match:
        due_date = date_match.group(1)
        text = text[:date_match.start()].strip() + ' ' + text[date_match.end():].strip()
        text = text.strip()
    elif '@today' in text.lower() or '@今天' in text:
        due_date = local_today_iso()
        text = re.sub(r'@today|@今天', '', text, flags=re.IGNORECASE).strip()
    elif '@tomorrow' in text.lower() or '@明天' in text:
        due_date = local_date_offset_iso(1)
        text = re.sub(r'@tomorrow|@明天', '', text, flags=re.IGNORECASE).strip()

    return text.strip(), priority, due_date, explicit_kind


# ── /reorder MUST be registered before /{task_id} so FastAPI doesn't
#    try to parse the literal "reorder" as an int path parameter.
@router.put("/reorder")
def reorder_tasks(payload: ReorderRequest, request: Request):
    ordered_ids = payload.ordered_task_ids

    with get_db() as db:
        user = require_current_user(db, request)
        tasks = db.query(Task).filter(Task.user_id == user.id, Task.id.in_(ordered_ids)).all()
        task_by_id = {t.id: t for t in tasks}
        for idx, task_id in enumerate(ordered_ids):
            task = task_by_id.get(int(task_id))
            if task:
                task.sort_order = idx
                task.source = "manual"
                task.decision_reason = "Task manually reordered by user."
        db.flush()
        return {"message": "Tasks reordered", "count": len(ordered_ids)}


@router.put("/{task_id}")
def update_task(task_id: int, payload: TaskUpdateRequest, request: Request):
    with get_db() as db:
        user = require_current_user(db, request)
        task = db.get(Task, task_id)
        if not task or task.user_id != user.id:
            raise HTTPException(status_code=404, detail={"error_code": "TASK_NOT_FOUND", "message": "Task not found"})

        previous_status = task.status
        today_key = local_today_iso()

        if payload.title is not None:
            task.title = payload.title.strip()
        if payload.description is not None:
            task.description = payload.description.strip()
        if payload.priority is not None:
            task.priority = payload.priority
        if payload.sort_order is not None:
            task.sort_order = int(payload.sort_order)
        if payload.category is not None:
            task.category = payload.category
            task.source = "manual"
            task.decision_reason = "Category updated by user."
        if payload.due_date is not None:
            task.due_date = normalize_date_string(payload.due_date) if payload.due_date else None
        if payload.task_kind is not None:
            task.task_kind = normalize_task_kind(payload.task_kind)
        if payload.recurrence_weekday is not None:
            task.recurrence_weekday = normalize_recurrence_weekday(payload.recurrence_weekday)
        if payload.status is not None:
            if payload.status == TaskStatus.COMPLETED.value and _is_recurring(task):
                task.status = TaskStatus.ACTIVE.value
            else:
                task.status = payload.status

        if payload.title is not None and payload.task_kind is None:
            clean_title, marker_kind = strip_task_kind_markers(task.title)
            task.title = clean_title
            task.task_kind = infer_task_kind(task.title, task.description, task.due_date, marker_kind or task.task_kind)
            task.recurrence_weekday = infer_recurrence_weekday(task.title, task.description, None) if task.task_kind == "weekly" else None
        elif payload.task_kind is not None and task.task_kind != "weekly":
            task.recurrence_weekday = None
        elif payload.task_kind is not None and task.task_kind == "weekly" and task.recurrence_weekday is None:
            task.recurrence_weekday = infer_recurrence_weekday(task.title, task.description, None)
        if payload.deferral_count_delta:
            task.deferral_count += int(payload.deferral_count_delta)
            target_due = task.due_date or local_date_offset_iso(1)
            db.add(TaskHistory(
                task_id=task.id,
                date=local_today_iso(),
                action=HistoryAction.DEFERRED.value,
                ai_reasoning=f"Task deferred to {target_due} by user (total deferrals: {task.deferral_count}).",
            ))

        is_recurring = _is_recurring(task)
        already_completed_today = bool(
            task.completed_at and (
                (task.completed_at if task.completed_at.tzinfo else task.completed_at.replace(tzinfo=timezone.utc))
                .astimezone(APP_TIMEZONE)
                .date()
                .isoformat()
                == today_key
            )
        )
        should_complete = bool(
            payload.status == TaskStatus.COMPLETED.value and not already_completed_today
        )
        should_delete = bool(
            payload.status == TaskStatus.DELETED.value and payload.status != previous_status
        )
        should_restore = bool(
            payload.status == TaskStatus.ACTIVE.value and (task.completed_at is not None or task.deleted_at is not None)
        )

        if should_complete or should_delete or should_restore:
            if should_complete:
                task.completion_count += 1
                task.completed_at = datetime.now(timezone.utc)
                task.source = "manual"
                task.decision_reason = (
                    "Recurring task completed for this cycle by user."
                    if is_recurring
                    else "Marked as completed by user."
                )
                db.add(TaskHistory(
                    task_id=task.id,
                    date=today_key,
                    action=HistoryAction.COMPLETED.value,
                    ai_reasoning=(
                        "Recurring task completed by user for this cycle."
                        if is_recurring
                        else "Task completed by user."
                    ),
                ))
            elif should_delete:
                task.deleted_at = datetime.now(timezone.utc)
                task.source = "manual"
                task.decision_reason = "Deleted by user."
                db.add(TaskHistory(
                    task_id=task.id,
                    date=today_key,
                    action=HistoryAction.DELETED.value,
                    ai_reasoning="Task deleted by user.",
                ))
            elif should_restore:
                # Restore: clear completed_at and deleted_at
                task.completed_at = None
                task.deleted_at = None
                task.source = "manual"
                task.decision_reason = "Restored to active by user."
                db.add(TaskHistory(
                    task_id=task.id,
                    date=today_key,
                    action=HistoryAction.RESTORED.value,
                    ai_reasoning="Task restored to active.",
                ))

        db.flush()
        return task.to_dict()


@router.delete("/{task_id}")
def delete_task(task_id: int, request: Request, hard: bool = Query(default=False)):
    with get_db() as db:
        user = require_current_user(db, request)
        task = db.get(Task, task_id)
        if not task or task.user_id != user.id:
            raise HTTPException(status_code=404, detail={"error_code": "TASK_NOT_FOUND", "message": "Task not found"})

        if hard or task.status == TaskStatus.DELETED.value:
            from database.models import FocusSession
            db.query(FocusSession).filter(FocusSession.task_id == task_id).update(
                {"task_id": None}, synchronize_session=False
            )
            db.delete(task)
            db.flush()
            return {"message": "Task permanently deleted", "task_id": task_id}

        task.status = TaskStatus.DELETED.value
        task.deleted_at = datetime.now(timezone.utc)
        task.source = "manual"
        task.decision_reason = "Deleted by user."
        db.add(TaskHistory(
            task_id=task.id,
            date=local_today_iso(),
            action=HistoryAction.DELETED.value,
            ai_reasoning="Task deleted by user.",
        ))
        db.flush()
        return {"message": "Task deleted", "task": task.to_dict()}
