"""LLM service factory with pluggable providers and runtime configuration."""

import json
import logging
import os
from typing import Any, Dict

from core.llm.base import BaseLLMService
from core.llm.claude_provider import ClaudeLLMService
from core.llm.deepseek_provider import DeepSeekLLMService
from core.llm.mock import MockLLMService
from core.llm.openai_provider import OpenAILLMService

logger = logging.getLogger("deletion-planner-llm")

_runtime_config: Dict[str, str] = {}
_db_loaded = False


def _load_from_db() -> None:
    """Load LLM config from app_settings table once."""

    global _db_loaded
    if _db_loaded:
        return

    try:
        from database.db import get_db
        from database.models import AppSetting

        with get_db() as db:
            row = db.query(AppSetting).filter(AppSetting.key == "llm_config").first()
            if row and row.value:
                saved = json.loads(row.value)
                for key in ("provider", "api_key", "model"):
                    if key in saved and saved[key]:
                        _runtime_config[key] = saved[key]
                logger.info(
                    "LLM config loaded from database (provider=%s)",
                    saved.get("provider", ""),
                )
        _db_loaded = True
    except Exception as exc:
        logger.warning("Could not load LLM config from DB: %s", exc)
        _db_loaded = True


def _save_to_db() -> None:
    """Persist current runtime config to app_settings table."""

    try:
        from database.db import get_db
        from database.models import AppSetting

        config = {key: _runtime_config.get(key, "") for key in ("provider", "api_key", "model")}
        with get_db() as db:
            row = db.query(AppSetting).filter(AppSetting.key == "llm_config").first()
            if row:
                row.value = json.dumps(config)
            else:
                db.add(AppSetting(key="llm_config", value=json.dumps(config)))
            db.flush()
    except Exception as exc:
        logger.warning("Could not save LLM config to DB: %s", exc)


def get_runtime_config() -> Dict[str, str]:
    """Return merged config: runtime overrides > DB > env vars > defaults."""

    _load_from_db()
    return {
        "provider": _runtime_config.get("provider") or os.getenv("LLM_PROVIDER", "mock"),
        "api_key": (
            _runtime_config.get("api_key")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or ""
        ),
        "model": (
            _runtime_config.get("model")
            or os.getenv("OPENAI_MODEL")
            or os.getenv("ANTHROPIC_MODEL")
            or os.getenv("DEEPSEEK_MODEL")
            or ""
        ),
    }


def set_runtime_config(updates: Dict[str, Any]) -> None:
    """Update runtime LLM settings, sync env vars, and persist to DB."""

    for key in ("provider", "api_key", "model"):
        if key in updates:
            _runtime_config[key] = str(updates[key])

    config = get_runtime_config()
    provider = config["provider"].lower().strip()
    api_key = config["api_key"]
    model = config["model"]

    os.environ["LLM_PROVIDER"] = provider
    if provider == "openai":
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        if model:
            os.environ["OPENAI_MODEL"] = model
    elif provider == "claude":
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
        if model:
            os.environ["ANTHROPIC_MODEL"] = model
    elif provider == "deepseek":
        if api_key:
            os.environ["DEEPSEEK_API_KEY"] = api_key
        if model:
            os.environ["DEEPSEEK_MODEL"] = model

    _save_to_db()


def get_llm_service(lang: str = "en") -> BaseLLMService:
    """Return the configured LLM provider."""

    config = get_runtime_config()
    provider = config["provider"].lower().strip()

    if provider == "openai":
        return OpenAILLMService(lang=lang)
    if provider == "claude":
        return ClaudeLLMService(lang=lang)
    if provider == "deepseek":
        return DeepSeekLLMService(lang=lang)
    return MockLLMService(lang=lang)
