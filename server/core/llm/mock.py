"""Deterministic mock provider that mimics structured LLM outputs."""

from __future__ import annotations

from typing import Any, Dict, List

from core.llm.base import BaseLLMService


class MockLLMService(BaseLLMService):
    """Rule-following mock used for local development and testing."""

    def recommend_decisions(self, context: Dict[str, Any]) -> Dict[str, Any]:
        tasks: List[Dict[str, Any]] = context.get("tasks", [])
        rule_snapshot: Dict[str, Any] = context.get("rule_snapshot", {})

        selected_ids = list(rule_snapshot.get("selected_task_ids", []))
        deferred_ids = list(rule_snapshot.get("deferred_task_ids", []))
        candidates = list(rule_snapshot.get("deletion_candidates", []))

        # Mock behavior: trust rule layer and add top deletion candidates.
        delete_items = []
        for item in candidates[:3]:
            task_id = int(item["task_id"])
            task_title = ""
            for task in tasks:
                if int(task["id"]) == task_id:
                    task_title = task.get("title", "")
                    break
            reason = f'Rule signals repeated low commitment for "{task_title or task_id}".'
            delete_items.append({"task_id": task_id, "reason": reason})

        capacity = int(rule_snapshot.get("capacity_units", 0) or 0)
        required = int(rule_snapshot.get("required_units", 0) or 0)
        overload = int(rule_snapshot.get("overload_units", 0) or 0)
        reasoning = (
            f"Capacity is {capacity} units and required work is {required}. "
            f"{'Plan is overloaded; cut commitments.' if overload > 0 else 'Plan fits current capacity.'}"
        )

        return {
            "keep": selected_ids,
            "defer": deferred_ids,
            "delete": delete_items,
            "reasoning": reasoning,
            "confidence": 0.65,
        }

    def generate_deletion_reasoning(
        self, task: Dict[str, Any], rule_reasons: List[str]
    ) -> str:
        title = task.get("title", "This task")
        base = f'Consider deleting "{title}".'
        if rule_reasons:
            return f'{base} Reasons: {" ".join(rule_reasons)}'
        return base
