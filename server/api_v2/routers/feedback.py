from datetime import date
from fastapi import APIRouter, HTTPException

from api_v2.schemas import FeedbackSubmitRequest
from core.deletion import check_deletion_candidates
from database.db import get_db
from database.models import (
    Task, DailyPlan, PlanTask, TaskHistory,
    TaskStatus, PlanTaskStatus, HistoryAction,
)

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("")
def submit_feedback(payload: FeedbackSubmitRequest):
    target_date = payload.date or date.today().isoformat()
    if not payload.results:
        raise HTTPException(status_code=400, detail={"error_code": "EMPTY_FEEDBACK", "message": "No feedback results provided"})

    with get_db() as db:
        plan = db.query(DailyPlan).filter(DailyPlan.date == target_date).first()
        if not plan:
            raise HTTPException(status_code=404, detail={"error_code": "PLAN_NOT_FOUND", "message": "No plan found for this date"})

        for entry in payload.results:
            pt = db.query(PlanTask).get(entry.plan_task_id)
            if not pt or pt.plan_id != plan.id:
                continue

            new_status = entry.status
            pt.status = new_status
            task = db.query(Task).get(pt.task_id)
            if not task:
                continue

            if new_status == PlanTaskStatus.COMPLETED.value:
                task.completion_count += 1
                task.status = TaskStatus.COMPLETED.value
                task.source = "manual"
                task.decision_reason = "Completed from daily feedback."
                action = HistoryAction.COMPLETED.value
                reasoning = "Task completed by user."
            elif new_status == PlanTaskStatus.MISSED.value:
                action = HistoryAction.MISSED.value
                reasoning = "Task was planned but not completed."
            elif new_status == PlanTaskStatus.DEFERRED.value:
                task.deferral_count += 1
                task.source = "manual"
                task.decision_reason = "Deferred from daily feedback."
                action = HistoryAction.DEFERRED.value
                reasoning = f"Task deferred (total deferrals: {task.deferral_count})."
            else:
                continue

            db.add(TaskHistory(
                task_id=task.id,
                date=target_date,
                action=action,
                ai_reasoning=reasoning,
            ))

        db.flush()
        active_tasks = db.query(Task).filter(Task.status == TaskStatus.ACTIVE.value).all()
        deletion_suggestions = check_deletion_candidates(active_tasks, lang=payload.lang)

    return {"message": "Feedback recorded", "deletion_suggestions": deletion_suggestions}
