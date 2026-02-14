"""Core planning engine — selects tasks for a daily plan using the LLM service."""

from typing import List, Dict, Any
from core.llm import get_llm_service

# Maximum number of core tasks in a daily plan
DEFAULT_MAX_TASKS = 4


def generate_daily_plan(tasks, target_date: str, lang: str = "en") -> Dict[str, Any]:
    """Generate a daily plan from a list of active Task ORM objects.

    Args:
        tasks: List of Task ORM objects.
        target_date: ISO date string (YYYY-MM-DD).
        lang: Language code ("en" or "zh") for bilingual output.

    Returns a dict with:
        - selected_tasks: list of tasks chosen for today
        - deferred_tasks: list of tasks not selected
        - deletion_suggestions: tasks that should be considered for deletion
        - reasoning: AI-generated explanation
        - overload_warning: warning if user has too many tasks
        - max_tasks: the cap used
    """
    llm = get_llm_service(lang=lang)

    # Convert ORM objects to dicts for the LLM service
    task_dicts = [t.to_dict() for t in tasks]

    # Step 1: Classify all tasks
    classifications = llm.classify_tasks(task_dicts)
    category_map = {c["task_id"]: c for c in classifications}

    # Step 2: Separate into buckets
    core_tasks = []
    deferrable_tasks = []
    deletion_candidates = []

    for t in tasks:
        info = category_map.get(t.id, {})
        cat = info.get("category", "core")
        t_dict = t.to_dict()
        t_dict["ai_category"] = cat
        t_dict["ai_reason"] = info.get("reason", "")

        if cat == "deletion_candidate":
            deletion_candidates.append(t_dict)
        elif cat == "deferrable":
            deferrable_tasks.append(t_dict)
        else:
            core_tasks.append(t_dict)

    # Step 3: Select tasks for today (up to max)
    max_tasks = DEFAULT_MAX_TASKS
    selected = core_tasks[:max_tasks]

    # If we have fewer core tasks than max, fill from deferrable
    if len(selected) < max_tasks:
        remaining = max_tasks - len(selected)
        selected.extend(deferrable_tasks[:remaining])
        deferrable_tasks = deferrable_tasks[remaining:]

    # Anything not selected from core goes to deferred too
    deferred_core = core_tasks[max_tasks:]
    all_deferred = deferred_core + deferrable_tasks

    # Step 4: Build overload warning
    total_active = len(task_dicts)
    overload_warning = ""
    if total_active > max_tasks * 2:
        if lang == "zh":
            overload_warning = (
                f"你有 {total_active} 个活跃任务，但今天的计划只包含 "
                f"{len(selected)} 个。考虑审视并删除不再符合你目标的任务。"
            )
        else:
            overload_warning = (
                f"You have {total_active} active tasks but today's plan only includes "
                f"{len(selected)}. Consider reviewing and deleting tasks that no longer "
                f"serve your goals."
            )

    # Step 5: Generate deletion suggestions
    deletion_suggestions = []
    for dc in deletion_candidates:
        dc["deletion_reasoning"] = llm.generate_deletion_reasoning(dc)
        deletion_suggestions.append(dc)

    # Step 6: Generate overall reasoning
    reasoning = llm.generate_plan_reasoning(
        selected, all_deferred, deletion_suggestions
    )

    # Format selected tasks for the response
    selected_formatted = [
        {
            "task_id": t["id"],
            "reason": t.get("ai_reason", ""),
            "category": t.get("ai_category", "unclassified"),
        }
        for t in selected
    ]

    classified_tasks = [
        {
            "task_id": t.id,
            "category": category_map.get(t.id, {}).get("category", "unclassified"),
        }
        for t in tasks
    ]

    return {
        "selected_tasks": selected_formatted,
        "deferred_tasks": all_deferred,
        "deletion_suggestions": deletion_suggestions,
        "reasoning": reasoning,
        "overload_warning": overload_warning,
        "max_tasks": max_tasks,
        "classified_tasks": classified_tasks,
    }


def regenerate_reasoning(plan, all_active_tasks, lang: str = "en") -> Dict[str, Any]:
    """Re-generate reasoning and overload_warning for an existing plan in the given language.

    This is used when the user switches language after a plan was already generated.
    The task selections stay the same — only the text is re-translated.

    Args:
        plan: DailyPlan ORM object (with plan_tasks loaded).
        all_active_tasks: List of all active Task ORM objects.
        lang: Language code.

    Returns:
        Dict with "reasoning", "overload_warning", "deletion_suggestions".
    """
    llm = get_llm_service(lang=lang)

    # Gather selected tasks (from plan) and figure out deferred tasks
    selected_task_ids = {pt.task_id for pt in plan.plan_tasks}
    selected_dicts = []
    deferred_dicts = []

    for t in all_active_tasks:
        t_dict = t.to_dict()
        if t.id in selected_task_ids:
            selected_dicts.append(t_dict)
        else:
            deferred_dicts.append(t_dict)

    # Also classify to find deletion candidates
    all_dicts = [t.to_dict() for t in all_active_tasks]
    classifications = llm.classify_tasks(all_dicts)
    deletion_candidates = []
    for c in classifications:
        if c["category"] == "deletion_candidate":
            # Find the task dict
            for td in all_dicts:
                if td["id"] == c["task_id"]:
                    td["deletion_reasoning"] = llm.generate_deletion_reasoning(td)
                    deletion_candidates.append(td)
                    break

    # Generate reasoning
    reasoning = llm.generate_plan_reasoning(
        selected_dicts, deferred_dicts, deletion_candidates
    )

    # Generate overload warning
    total_active = len(all_active_tasks)
    num_selected = len(selected_dicts)
    overload_warning = ""
    if total_active > DEFAULT_MAX_TASKS * 2:
        if lang == "zh":
            overload_warning = (
                f"你有 {total_active} 个活跃任务，但今天的计划只包含 "
                f"{num_selected} 个。考虑审视并删除不再符合你目标的任务。"
            )
        else:
            overload_warning = (
                f"You have {total_active} active tasks but today's plan only includes "
                f"{num_selected}. Consider reviewing and deleting tasks that no longer "
                f"serve your goals."
            )

    return {
        "reasoning": reasoning,
        "overload_warning": overload_warning,
        "deletion_suggestions": deletion_candidates,
    }
