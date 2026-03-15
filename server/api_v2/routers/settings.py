"""Runtime LLM configuration endpoint."""

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from api_v2.user_context import require_current_user
from core.llm import get_runtime_config, set_runtime_config
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
        db.flush()
        return {"ok": True, "message": "Developer reset completed"}
