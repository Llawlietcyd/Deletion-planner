"""Mood check-in endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from api_v2.schemas import MoodCreateRequest
from api_v2.user_context import require_current_user
from database.db import get_db
from database.models import MoodEntry
from core.time import datetime_to_iso, local_date_offset, local_today_iso

router = APIRouter(tags=["mood"])


@router.post("/mood")
def submit_mood(payload: MoodCreateRequest, request: Request):
    today = local_today_iso()
    with get_db() as db:
        user = require_current_user(db, request)
        entry = MoodEntry(
            user_id=user.id,
            date=today,
            mood_level=payload.mood_level,
            note=payload.note,
        )
        db.add(entry)
        db.flush()
        return {
            "id": entry.id,
            "date": entry.date,
            "mood_level": entry.mood_level,
            "note": entry.note,
            "created_at": datetime_to_iso(entry.created_at),
        }


@router.get("/mood/today")
def get_today_mood(request: Request):
    today = local_today_iso()
    with get_db() as db:
        user = require_current_user(db, request)
        entry = (
            db.query(MoodEntry)
            .filter(MoodEntry.user_id == user.id, MoodEntry.date == today)
            .order_by(MoodEntry.created_at.desc(), MoodEntry.id.desc())
            .first()
        )
        if not entry:
            return {"mood_level": None, "note": "", "date": today}
        return {
            "id": entry.id,
            "date": entry.date,
            "mood_level": entry.mood_level,
            "note": entry.note,
            "created_at": datetime_to_iso(entry.created_at),
        }


@router.get("/mood/history")
def get_mood_history(request: Request, days: int = 30):
    with get_db() as db:
        user = require_current_user(db, request)
        cutoff = local_date_offset(-days).isoformat()
        entries = (
            db.query(MoodEntry)
            .filter(MoodEntry.user_id == user.id, MoodEntry.date >= cutoff)
            .order_by(MoodEntry.created_at.desc(), MoodEntry.id.desc())
            .all()
        )
        return [
            {
                "id": e.id,
                "date": e.date,
                "mood_level": e.mood_level,
                "note": e.note,
                "created_at": datetime_to_iso(e.created_at),
            }
            for e in entries
        ]
