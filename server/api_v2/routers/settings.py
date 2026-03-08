"""Runtime LLM configuration endpoint."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.llm import get_runtime_config, set_runtime_config

router = APIRouter(prefix="/settings", tags=["settings"])


class LLMConfigUpdate(BaseModel):
    provider: Optional[str] = None  # mock | openai | claude | deepseek
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
        "provider": config.get("provider", "mock"),
        "model": config.get("model", ""),
        "api_key_set": bool(config.get("api_key")),
        "api_key_masked": masked_key,
    }


@router.put("/llm")
def update_llm_config(payload: LLMConfigUpdate):
    """Update LLM provider configuration at runtime."""

    updates = {}
    if payload.provider is not None:
        provider = payload.provider.lower().strip()
        if provider not in ("mock", "openai", "claude", "deepseek"):
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "INVALID_PROVIDER",
                    "message": "Provider must be mock, openai, claude, or deepseek",
                },
            )
        updates["provider"] = provider
    if payload.api_key is not None:
        updates["api_key"] = payload.api_key.strip()
    if payload.model is not None:
        updates["model"] = payload.model.strip()

    set_runtime_config(updates)
    return get_llm_config()


@router.post("/llm/test")
def test_llm_connection():
    """Quick smoke test against the configured provider."""

    config = get_runtime_config()
    provider = config.get("provider", "mock")

    if provider == "mock":
        return {"ok": True, "provider": "mock", "message": "Mock provider is active; no external API call needed."}

    try:
        if provider == "openai":
            from core.llm.openai_provider import OpenAILLMService

            llm = OpenAILLMService(lang="en")
            raw = llm._call_openai(
                "You are a helpful assistant.",
                "Reply with exactly: CONNECTION_OK",
                max_tokens=16,
            )
            return {"ok": True, "provider": provider, "message": raw[:200]}
        if provider == "claude":
            from core.llm.claude_provider import ClaudeLLMService

            llm = ClaudeLLMService(lang="en")
            raw = llm._call_claude(
                "You are a helpful assistant.",
                "Reply with exactly: CONNECTION_OK",
                max_tokens=16,
            )
            return {"ok": True, "provider": provider, "message": raw[:200]}
        if provider == "deepseek":
            from core.llm.deepseek_provider import DeepSeekLLMService

            llm = DeepSeekLLMService(lang="en")
            raw = llm._call_deepseek(
                "You are a helpful assistant.",
                "Reply with exactly: CONNECTION_OK",
                max_tokens=16,
            )
            return {"ok": True, "provider": provider, "message": raw[:200]}
        return {"ok": False, "provider": provider, "message": "Unknown provider"}
    except Exception as exc:
        return {"ok": False, "provider": provider, "message": str(exc)[:300]}
