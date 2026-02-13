"""LLM service factory."""

import os
from core.llm.base import BaseLLMService
from core.llm.mock import MockLLMService


def get_llm_service(lang="en") -> BaseLLMService:
    """Return the configured LLM service instance.

    Args:
        lang: Language code ("en" or "zh") for bilingual output.

    Set LLM_PROVIDER env var to switch:
      - "mock"   -> rule-based mock (default)
      - "claude" -> Claude API (future)
      - "openai" -> OpenAI API (future)
    """
    provider = os.getenv("LLM_PROVIDER", "mock").lower()

    if provider == "mock":
        return MockLLMService(lang=lang)
    # Future: elif provider == "claude": return ClaudeLLMService(lang=lang)
    # Future: elif provider == "openai": return OpenAILLMService(lang=lang)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
