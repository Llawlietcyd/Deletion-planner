"""Runtime LLM configuration endpoint."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from api_v2.user_context import require_current_user
from core.llm import get_runtime_config, set_runtime_config
from core.showcase import load_protected_showcase_usernames
from database.db import get_db
from database.models import (
    AppSetting,
    DailyFortune,
    DailyPlan,
    FocusSession,
    MoodEntry,
    PlanTask,
    Task,
    TaskHistory,
    User,
    UserSession,
)

router = APIRouter(prefix="/settings", tags=["settings"])


class LLMConfigUpdate(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = None


def _setting_user_id(key: str) -> int | None:
    if ":" not in key:
        return None
    suffix = key.rsplit(":", 1)[-1].strip()
    if not suffix.isdigit():
        return None
    return int(suffix)


def _plan_user_id(storage_key: str) -> int | None:
    if ":" not in storage_key:
        return None
    prefix = storage_key.split(":", 1)[0].strip()
    if not prefix.isdigit():
        return None
    return int(prefix)


@router.get("/llm")
def get_llm_config():
    """Return current LLM provider configuration with a masked key."""

    config = get_runtime_config()
    masked_key = ""
    if config.get("api_key"):
        key = config["api_key"]
        masked_key = key[:8] + "..." + key[-4:] if len(key) > 12 else "****"
    return {
        "provider": "deepseek",
        "model": config.get("model", ""),
        "api_key_set": bool(config.get("api_key")),
        "api_key_masked": masked_key,
    }


@router.put("/llm")
def update_llm_config(payload: LLMConfigUpdate, request: Request):
    """Update LLM provider configuration at runtime."""

    with get_db() as db:
        require_current_user(db, request)

    updates = {}
    if payload.api_key is not None:
        updates["api_key"] = payload.api_key.strip()
    if payload.model is not None:
        updates["model"] = payload.model.strip()

    set_runtime_config(updates)
    return get_llm_config()


@router.post("/llm/test")
def test_llm_connection(request: Request):
    """Quick smoke test against the configured DeepSeek provider."""

    with get_db() as db:
        require_current_user(db, request)

    config = get_runtime_config()
    provider = "deepseek"

    try:
        from core.llm.deepseek_provider import DeepSeekLLMService

        llm = DeepSeekLLMService(lang="en")
        raw = llm._call_deepseek(
            "You are a helpful assistant.",
            "Reply with exactly: CONNECTION_OK",
            max_tokens=16,
        )
        return {"ok": True, "provider": provider, "message": raw[:200]}
    except Exception as exc:
        return {"ok": False, "provider": provider, "message": str(exc)[:300]}


@router.post("/developer/reset")
def developer_reset(request: Request):
    """Wipe local prototype data while preserving system-level settings."""

    with get_db() as db:
        require_current_user(db, request)
        protected_usernames = load_protected_showcase_usernames(db)
        protected_user_ids = {
            user.id
            for user in db.query(User).filter(User.username.in_(sorted(protected_usernames))).all()
        }

        if protected_user_ids:
            db.query(UserSession).filter(~UserSession.user_id.in_(protected_user_ids)).delete(synchronize_session=False)
            db.query(MoodEntry).filter(~MoodEntry.user_id.in_(protected_user_ids)).delete(synchronize_session=False)
            db.query(DailyFortune).filter(~DailyFortune.user_id.in_(protected_user_ids)).delete(synchronize_session=False)
            db.query(FocusSession).filter(~FocusSession.user_id.in_(protected_user_ids)).delete(synchronize_session=False)

            task_ids_to_delete = [
                row.id
                for row in db.query(Task.id).filter(~Task.user_id.in_(protected_user_ids)).all()
            ]
            if task_ids_to_delete:
                db.query(TaskHistory).filter(TaskHistory.task_id.in_(task_ids_to_delete)).delete(synchronize_session=False)
                db.query(Task).filter(Task.id.in_(task_ids_to_delete)).delete(synchronize_session=False)

            plan_ids_to_delete = [
                plan.id
                for plan in db.query(DailyPlan).all()
                if _plan_user_id(plan.date) not in protected_user_ids
            ]
            if plan_ids_to_delete:
                db.query(PlanTask).filter(PlanTask.plan_id.in_(plan_ids_to_delete)).delete(synchronize_session=False)
                db.query(DailyPlan).filter(DailyPlan.id.in_(plan_ids_to_delete)).delete(synchronize_session=False)

            db.query(User).filter(~User.id.in_(protected_user_ids)).delete(synchronize_session=False)

            settings_to_delete = []
            for row in db.query(AppSetting).filter(
                (AppSetting.key.like("prototype_onboarding:%"))
                | (AppSetting.key.like("assistant_profile:%"))
                | (AppSetting.key.like("assistant_history:%"))
                | (AppSetting.key.like("assistant_pending:%"))
            ).all():
                owner_id = _setting_user_id(row.key)
                if owner_id is None or owner_id not in protected_user_ids:
                    settings_to_delete.append(row.key)
            if settings_to_delete:
                db.query(AppSetting).filter(AppSetting.key.in_(settings_to_delete)).delete(synchronize_session=False)
            message = "Developer reset completed. Protected showcase data was preserved."
        else:
            db.query(UserSession).delete()
            db.query(MoodEntry).delete()
            db.query(DailyFortune).delete()
            db.query(FocusSession).delete()
            db.query(TaskHistory).delete()
            db.query(PlanTask).delete()
            db.query(Task).delete()
            db.query(DailyPlan).delete()
            db.query(User).delete()
            db.query(AppSetting).filter(
                (AppSetting.key.like("prototype_onboarding:%"))
                | (AppSetting.key.like("assistant_profile:%"))
                | (AppSetting.key.like("assistant_history:%"))
                | (AppSetting.key.like("assistant_pending:%"))
            ).delete(synchronize_session=False)
            message = "Developer reset completed"
        db.flush()
        return {"ok": True, "message": message}
