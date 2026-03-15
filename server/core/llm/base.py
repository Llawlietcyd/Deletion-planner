"""Abstract base class for pluggable LLM decision providers."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseLLMService(ABC):
    """Provider interface for AI decision support.

    The rule layer remains deterministic. LLM providers only return
    structured recommendations that are validated by guardrails.
    """

    def __init__(self, lang: str = "en"):
        self.lang = lang

    @abstractmethod
    def recommend_decisions(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Return structured plan decisions.

        Expected shape:
            {
                "keep": [task_id, ...],
                "defer": [task_id, ...],
                "delete": [{"task_id": int, "reason": str}, ...],
                "reasoning": str,
                "confidence": float
            }
        """
        ...

    @abstractmethod
    def generate_deletion_reasoning(
        self, task: Dict[str, Any], rule_reasons: List[str]
    ) -> str:
        """Generate a user-facing deletion explanation for one task."""
        ...

    def recommend_songs(
        self, mood_level: int, task_count: int, lang: str = "en",
        mood_note: str = "", top_tasks: str = "", refresh_token: str = "",
        exclude_songs: Optional[List[str]] = None
    ) -> List[Dict[str, str]]:
        """Return song recommendations. Default falls back to mock data."""
        from core.llm.mock import MockLLMService
        return MockLLMService(lang=lang).recommend_songs(
            mood_level,
            task_count,
            lang,
            mood_note=mood_note,
            top_tasks=top_tasks,
            refresh_token=refresh_token,
            exclude_songs=exclude_songs,
        )

    def generate_fortune(
        self, birthday: str, current_date: str, lang: str = "en",
        zodiac: Dict[str, str] = None, user_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Generate daily fortune. Default falls back to mock data."""
        from core.llm.mock import MockLLMService
        return MockLLMService(lang=lang).generate_fortune(
            birthday, current_date, lang, zodiac=zodiac, user_context=user_context
        )
