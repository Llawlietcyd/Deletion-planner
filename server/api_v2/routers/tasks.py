from datetime import date, datetime, timezone
from fastapi import APIRouter, HTTPException, Query

from api_v2.schemas import TaskCreateRequest, TaskUpdateRequest, TaskBatchCreateRequest, ReorderRequest
from database.db import get_db
from database.models import Task, TaskHistory, TaskStatus, HistoryAction

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
def list_tasks(status: str = Query(default="active"), q: str = Query(default="")):
    with get_db() as db:
        query = db.query(Task)
        if status != "all":
            query = query.filter(Task.status == status)
        if q.strip():
            keyword = f"%{q.strip()}%"
            query = query.filter(
                (Task.title.ilike(keyword)) | (Task.description.ilike(keyword))
            )
        return [t.to_dict() for t in query.order_by(Task.sort_order.asc(), Task.priority.desc(), Task.created_at.desc()).all()]


@router.post("", status_code=201)
def create_task(payload: TaskCreateRequest):
    with get_db() as db:
        task = Task(
            title=payload.title.strip(),
            description=payload.description.strip(),
            priority=payload.priority,
            sort_order=payload.sort_order,
            category=payload.category,
            due_date=payload.due_date,
            source="manual",
            decision_reason="User-created task.",
        )
        db.add(task)
        db.flush()

        db.add(TaskHistory(
            task_id=task.id,
            date=date.today().isoformat(),
            action=HistoryAction.CREATED.value,
            ai_reasoning="Task created by user.",
        ))
        db.flush()
        return task.to_dict()


@router.post("/batch", status_code=201)
def batch_create_tasks(payload: TaskBatchCreateRequest):
    lines = [line.strip() for line in payload.text.splitlines() if line.strip()]
    if not lines:
        raise HTTPException(status_code=400, detail={"error_code": "INVALID_BATCH", "message": "No tasks provided"})

    created = []
    with get_db() as db:
        for line in lines:
            title, priority, due_date = _parse_task_line(line)
            task = Task(title=title, priority=priority, due_date=due_date)
            db.add(task)
            db.flush()
            db.add(TaskHistory(
                task_id=task.id,
                date=date.today().isoformat(),
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
    text = line

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
        due_date = date.today().isoformat()
        text = re.sub(r'@today|@今天', '', text, flags=re.IGNORECASE).strip()
    elif '@tomorrow' in text.lower() or '@明天' in text:
        from datetime import timedelta
        due_date = (date.today() + timedelta(days=1)).isoformat()
        text = re.sub(r'@tomorrow|@明天', '', text, flags=re.IGNORECASE).strip()

    return text.strip(), priority, due_date


# ── /reorder MUST be registered before /{task_id} so FastAPI doesn't
#    try to parse the literal "reorder" as an int path parameter.
@router.put("/reorder")
def reorder_tasks(payload: ReorderRequest):
    ordered_ids = payload.ordered_task_ids

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
        return {"message": "Tasks reordered", "count": len(ordered_ids)}


@router.put("/{task_id}")
def update_task(task_id: int, payload: TaskUpdateRequest):
    with get_db() as db:
        task = db.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail={"error_code": "TASK_NOT_FOUND", "message": "Task not found"})

        previous_status = task.status

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
            task.due_date = payload.due_date if payload.due_date else None
        if payload.status is not None:
            task.status = payload.status
        if payload.deferral_count_delta:
            task.deferral_count += int(payload.deferral_count_delta)
            db.add(TaskHistory(
                task_id=task.id,
                date=date.today().isoformat(),
                action=HistoryAction.DEFERRED.value,
                ai_reasoning=f"Task deferred (total deferrals: {task.deferral_count}).",
            ))

        if payload.status and payload.status != previous_status:
            if payload.status == TaskStatus.COMPLETED.value:
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
            elif payload.status == TaskStatus.DELETED.value:
                task.deleted_at = datetime.now(timezone.utc)
                task.source = "manual"
                task.decision_reason = "Deleted by user."
                db.add(TaskHistory(
                    task_id=task.id,
                    date=date.today().isoformat(),
                    action=HistoryAction.DELETED.value,
                    ai_reasoning="Task deleted by user.",
                ))
            elif payload.status == TaskStatus.ACTIVE.value:
                # Restore: clear completed_at and deleted_at
                task.completed_at = None
                task.deleted_at = None
                task.source = "manual"
                task.decision_reason = "Restored to active by user."
                db.add(TaskHistory(
                    task_id=task.id,
                    date=date.today().isoformat(),
                    action=HistoryAction.CREATED.value,
                    ai_reasoning="Task restored to active.",
                ))

        db.flush()
        return task.to_dict()


@router.delete("/{task_id}")
def delete_task(task_id: int, hard: bool = Query(default=False)):
    with get_db() as db:
        task = db.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail={"error_code": "TASK_NOT_FOUND", "message": "Task not found"})

        if hard or task.status == TaskStatus.DELETED.value:
            db.delete(task)
            db.flush()
            return {"message": "Task permanently deleted", "task_id": task_id}

        task.status = TaskStatus.DELETED.value
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
        return {"message": "Task deleted", "task": task.to_dict()}
