"""Deletion detection engine — identifies tasks that should be considered for removal."""

from typing import List, Dict, Any
from core.llm import get_llm_service

# Thresholds
DEFERRAL_THRESHOLD = 3       # Suggest deletion after this many deferrals
LOW_COMPLETION_RATE = 0.3    # Flag tasks with completion rate below 30%


def check_deletion_candidates(tasks, lang: str = "en") -> List[Dict[str, Any]]:
    """Scan active tasks and return deletion suggestions.

    Args:
        tasks: List of Task ORM objects.
        lang: Language code ("en" or "zh") for bilingual output.

    Returns:
        List of dicts with task info + deletion_reasoning.
    """
    llm = get_llm_service(lang=lang)
    suggestions = []

    for task in tasks:
        should_suggest = False
        reason_parts = []

        # Rule 1: High deferral count
        if task.deferral_count >= DEFERRAL_THRESHOLD:
            should_suggest = True
            if lang == "zh":
                reason_parts.append(f"已推迟 {task.deferral_count} 次")
            else:
                reason_parts.append(f"Deferred {task.deferral_count} times")

        # Rule 2: Low completion rate (only if planned enough times)
        total_attempts = task.completion_count + task.deferral_count
        if total_attempts >= 3:
            rate = task.completion_count / total_attempts
            if rate < LOW_COMPLETION_RATE:
                should_suggest = True
                if lang == "zh":
                    reason_parts.append(
                        f"完成率为 {rate:.0%}（{task.completion_count}/{total_attempts}）"
                    )
                else:
                    reason_parts.append(
                        f"Completion rate is {rate:.0%} ({task.completion_count}/{total_attempts})"
                    )

        if should_suggest:
            t_dict = task.to_dict()
            t_dict["trigger_reasons"] = reason_parts
            t_dict["deletion_reasoning"] = llm.generate_deletion_reasoning(t_dict)
            suggestions.append(t_dict)

    return suggestions
