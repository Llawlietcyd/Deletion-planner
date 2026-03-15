"""Helpers for token-based user session and user-scoped storage keys."""

from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import HTTPException
from fastapi import Request

from database.models import AppSetting, User, UserSession

ONBOARDING_KEY_PREFIX = "prototype_onboarding"


def read_setting(db, key: str, default: Dict[str, Any]) -> Dict[str, Any]:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if not row or not row.value:
        return dict(default)
    try:
        data = json.loads(row.value)
        if isinstance(data, dict):
            merged = dict(default)
            merged.update(data)
            return merged
    except json.JSONDecodeError:
        pass
    return dict(default)


def write_setting(db, key: str, value: Dict[str, Any]) -> None:
    payload = json.dumps(value)
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = payload
    else:
        db.add(AppSetting(key=key, value=payload))
    db.flush()


def onboarding_key(user_id: int) -> str:
    return f"{ONBOARDING_KEY_PREFIX}:{user_id}"


def plan_storage_key(user_id: int, plan_date: str) -> str:
    return f"{user_id}:{plan_date}"


def get_session_token(request: Request) -> str:
    token = request.headers.get("X-Session-Token", "").strip()
    if token:
        return token
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return ""


def get_active_session(db, request: Request) -> UserSession | None:
    token = get_session_token(request)
    if not token:
        return None
    session = db.query(UserSession).filter(UserSession.token == token).first()
    if not session:
        return None
    return session


def get_session_state(db, request: Request) -> Dict[str, Any]:
    session = get_active_session(db, request)
    if not session or not session.user:
        return {"logged_in": False, "user_id": None, "display_name": "", "session_token": ""}
    return {
        "logged_in": True,
        "user_id": session.user.id,
        "display_name": session.user.username,
        "session_token": session.token,
    }


def require_current_user(db, request: Request) -> User:
    session = get_active_session(db, request)
    if not session or not session.user:
        raise HTTPException(
            status_code=401,
            detail={"error_code": "SESSION_REQUIRED", "message": "Log in first"},
        )
    return session.user
