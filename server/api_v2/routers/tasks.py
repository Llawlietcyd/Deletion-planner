from datetime import date, datetime, timezone
from fastapi import APIRouter, HTTPException, Query

from api_v2.schemas import TaskCreateRequest, TaskUpdateRequest, TaskBatchCreateRequest
from database.db import get_db
from database.models import Task, TaskHistory, TaskStatus, HistoryAction

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
def list_tasks(status: str = Query(default="active")):
    with get_db() as db:
        query = db.query(Task)
        if status != "all":
            query = query.filter(Task.status == status)
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
            task = Task(title=line)
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


@router.put("/{task_id}")
def update_task(task_id: int, payload: TaskUpdateRequest):
    with get_db() as db:
        task = db.query(Task).get(task_id)
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

        db.flush()
        return task.to_dict()


@router.put("/reorder")
def reorder_tasks(payload: dict):
    ordered_ids = payload.get("ordered_task_ids", [])
    if not isinstance(ordered_ids, list) or not ordered_ids:
        raise HTTPException(status_code=400, detail={"error_code": "INVALID_REORDER", "message": "ordered_task_ids must be a non-empty list"})

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


@router.delete("/{task_id}")
def delete_task(task_id: int, hard: bool = Query(default=False)):
    with get_db() as db:
        task = db.query(Task).get(task_id)
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
