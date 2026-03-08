"""Abstract base class for pluggable LLM decision providers."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List


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
