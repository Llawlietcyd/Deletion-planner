"""Abstract base class for LLM services."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseLLMService(ABC):
    """Interface that all LLM providers must implement."""

    def __init__(self, lang="en"):
        self.lang = lang

    @abstractmethod
    def classify_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Classify tasks into core / deferrable / deletion_candidate.

        Returns:
            List of dicts: [{"task_id": int, "category": str, "reason": str}, ...]
        """
        ...

    @abstractmethod
    def generate_plan_reasoning(
        self,
        selected_tasks: List[Dict[str, Any]],
        deferred_tasks: List[Dict[str, Any]],
        deletion_suggestions: List[Dict[str, Any]],
    ) -> str:
        """Generate a human-readable reasoning explanation for the daily plan."""
        ...

    @abstractmethod
    def generate_deletion_reasoning(self, task: Dict[str, Any]) -> str:
        """Generate a reasoning explanation for why a task should be deleted."""
        ...
