"""Deletion candidate detection built on deterministic rules."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.llm import get_llm_service
from core.rules import build_capacity_snapshot, localize_rule_reasons


def check_deletion_candidates(
    tasks,
    lang: str = "en",
    capacity_units: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return deletion suggestions for active tasks."""
    task_dicts = [task.to_dict() for task in tasks]
    snapshot = build_capacity_snapshot(task_dicts, capacity_units=capacity_units)
    candidate_map = {
        int(item["task_id"]): item for item in snapshot.get("deletion_candidates", [])
    }
    llm = get_llm_service(lang=lang)

    suggestions: List[Dict[str, Any]] = []
    for task in task_dicts:
        task_id = int(task["id"])
        candidate = candidate_map.get(task_id)
        if not candidate:
            continue
        rule_reasons = localize_rule_reasons(list(candidate.get("rule_reasons", [])), lang)
        suggestion = dict(task)
        suggestion["trigger_reasons"] = rule_reasons
        suggestion["deletion_reasoning"] = llm.generate_deletion_reasoning(
            task, rule_reasons
        )
        suggestions.append(suggestion)

    return suggestions
