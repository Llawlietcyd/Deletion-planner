"""Focus session (pomodoro) endpoints."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Request
from sqlalchemy import func

from fastapi import HTTPException

from api_v2.schemas import FocusSessionCreateRequest
from api_v2.user_context import require_current_user
from core.time import local_today, local_today_iso
from database.db import get_db
from database.models import FocusSession, Task

router = APIRouter(tags=["focus"])


@router.post("/focus/sessions")
def save_focus_session(payload: FocusSessionCreateRequest, request: Request):
    today = local_today_iso()
    with get_db() as db:
        user = require_current_user(db, request)
        if payload.task_id is not None:
            task = db.get(Task, payload.task_id)
            if not task or task.user_id != user.id:
                raise HTTPException(status_code=404, detail={"error_code": "TASK_NOT_FOUND", "message": "Task not found"})
        entry = FocusSession(
            user_id=user.id,
            task_id=payload.task_id,
            date=today,
            duration_minutes=payload.duration_minutes,
            session_type=payload.session_type,
        )
        db.add(entry)
        db.flush()
        return {
            "id": entry.id,
            "date": entry.date,
            "duration_minutes": entry.duration_minutes,
            "session_type": entry.session_type,
        }


@router.get("/focus/stats")
def get_focus_stats(request: Request):
    today = local_today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    today_str = today.isoformat()

    with get_db() as db:
        user = require_current_user(db, request)

        today_rows = (
            db.query(
                func.count(FocusSession.id),
                func.coalesce(func.sum(FocusSession.duration_minutes), 0),
            )
            .filter(
                FocusSession.user_id == user.id,
                FocusSession.date == today_str,
                FocusSession.session_type == "work",
            )
            .first()
        )

        week_rows = (
            db.query(
                func.count(FocusSession.id),
                func.coalesce(func.sum(FocusSession.duration_minutes), 0),
            )
            .filter(
                FocusSession.user_id == user.id,
                FocusSession.date >= week_start,
                FocusSession.session_type == "work",
            )
            .first()
        )

        total_rows = (
            db.query(
                func.count(FocusSession.id),
                func.coalesce(func.sum(FocusSession.duration_minutes), 0),
            )
            .filter(
                FocusSession.user_id == user.id,
                FocusSession.session_type == "work",
            )
            .first()
        )

        return {
            "today": {"sessions": today_rows[0], "minutes": int(today_rows[1])},
            "week": {"sessions": week_rows[0], "minutes": int(week_rows[1])},
            "total": {"sessions": total_rows[0], "minutes": int(total_rows[1])},
        }


@router.get("/focus/history")
def get_focus_history(request: Request, days: int = 90):
    today = local_today()
    start = (today - timedelta(days=max(1, days) - 1)).isoformat()

    with get_db() as db:
        user = require_current_user(db, request)
        rows = (
            db.query(FocusSession)
            .filter(
                FocusSession.user_id == user.id,
                FocusSession.date >= start,
            )
            .order_by(FocusSession.date.desc(), FocusSession.created_at.desc())
            .all()
        )
        return [
            {
                "id": row.id,
                "date": row.date,
                "task_id": row.task_id,
                "duration_minutes": row.duration_minutes,
                "session_type": row.session_type,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
