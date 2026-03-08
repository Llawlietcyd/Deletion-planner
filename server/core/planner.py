"""Capacity-aware planning engine with rule guardrails and pluggable LLM reasoning."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.llm import get_llm_service
from core.rules import build_capacity_snapshot, normalize_capacity_units


def _ordered_unique(ids: List[int], preferred_order: List[int]) -> List[int]:
    seen = set()
    rank = {task_id: idx for idx, task_id in enumerate(preferred_order)}
    ordered = sorted(ids, key=lambda item: rank.get(item, len(rank) + item))
    result = []
    for task_id in ordered:
        if task_id in seen:
            continue
        seen.add(task_id)
        result.append(task_id)
    return result


def _build_overload_warning(snapshot: Dict[str, Any], lang: str) -> str:
    overload_units = int(snapshot.get("overload_units", 0) or 0)
    hard_overload = int(snapshot.get("hard_commitment_overload", 0) or 0)
    capacity = int(snapshot.get("capacity_units", 0) or 0)
    required = int(snapshot.get("required_units", 0) or 0)

    if overload_units <= 0 and hard_overload <= 0:
        return ""

    if lang == "zh":
        if hard_overload > 0:
            return (
                f"硬性承诺需要 {required} 个单位，已经超过你当前 {capacity} 的容量上限。"
                f"先减少承诺，再考虑新增任务。"
            )
        return (
            f"当前任务大约需要 {required} 个单位，但容量只有 {capacity}。"
            f"至少要移出 {overload_units} 个单位的工作量。"
        )

    if hard_overload > 0:
        return (
            f"Hard commitments require {required} units, which exceeds your "
            f"capacity of {capacity}. Reduce commitments before adding work."
        )
    return (
        f"Current commitments require {required} units but capacity is {capacity}. "
        f"Remove at least {overload_units} units."
    )


def _apply_guardrails(
    ai_result: Dict[str, Any],
    snapshot: Dict[str, Any],
    all_task_ids: List[int],
) -> Dict[str, Any]:
    task_meta = snapshot.get("task_meta", {})
    capacity = int(snapshot.get("capacity_units", 0) or 0)
    rule_selected = list(snapshot.get("selected_task_ids", []))
    non_negotiable = set(snapshot.get("non_negotiable_task_ids", []))
    allowed_ids = set(all_task_ids)

    def _safe_int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    ai_keep: List[int] = []
    for value in ai_result.get("keep", []):
        maybe_id = _safe_int(value)
        if maybe_id is None or maybe_id not in allowed_ids:
            continue
        ai_keep.append(maybe_id)
    if not ai_keep:
        ai_keep = list(rule_selected)

    keep_ids = set(ai_keep)
    keep_ids.update(non_negotiable)

    def total_effort(ids: List[int]) -> int:
        return sum(int(task_meta.get(task_id, {}).get("effort_units", 1)) for task_id in ids)

    ordered_keep = _ordered_unique(list(keep_ids), preferred_order=rule_selected)

    while total_effort(ordered_keep) > capacity:
        removable = [task_id for task_id in ordered_keep if task_id not in non_negotiable]
        if not removable:
            break
        removable.sort(key=lambda task_id: task_meta.get(task_id, {}).get("keep_score", 0.0))
        ordered_keep = [task_id for task_id in ordered_keep if task_id != removable[0]]

    for task_id in rule_selected:
        if task_id in ordered_keep:
            continue
        candidate = ordered_keep + [task_id]
        if total_effort(candidate) <= capacity:
            ordered_keep.append(task_id)

    keep_set = set(ordered_keep)
    defer_ids = [task_id for task_id in all_task_ids if task_id not in keep_set]

    ai_delete = []
    for item in ai_result.get("delete", []):
        if not isinstance(item, dict):
            continue
        maybe_id = _safe_int(item.get("task_id", 0))
        if maybe_id is None or maybe_id <= 0:
            continue
        if maybe_id in non_negotiable or maybe_id in keep_set or maybe_id not in allowed_ids:
            continue
        ai_delete.append({"task_id": maybe_id, "reason": str(item.get("reason", "")).strip()})

    if not ai_delete:
        for candidate in snapshot.get("deletion_candidates", [])[:3]:
            task_id = int(candidate["task_id"])
            if task_id in keep_set:
                continue
            ai_delete.append({"task_id": task_id, "reason": ""})

    return {
        "keep_ids": ordered_keep,
        "defer_ids": defer_ids,
        "delete_items": ai_delete,
        "reasoning": str(ai_result.get("reasoning", "")).strip(),
        "confidence": float(ai_result.get("confidence", 0.0) or 0.0),
    }


def _build_deletion_suggestions(
    task_by_id: Dict[int, Dict[str, Any]],
    snapshot: Dict[str, Any],
    llm,
    delete_items: List[Dict[str, Any]],
    selected_ids: List[int],
) -> List[Dict[str, Any]]:
    candidate_map = {
        int(item["task_id"]): item for item in snapshot.get("deletion_candidates", [])
    }
    selected_set = set(selected_ids)

    suggestions: List[Dict[str, Any]] = []
    for item in delete_items:
        task_id = int(item["task_id"])
        if task_id in selected_set:
            continue
        task = task_by_id.get(task_id)
        if not task:
            continue
        rule_info = candidate_map.get(task_id, {})
        rule_reasons = list(rule_info.get("rule_reasons", []))
        suggestion = dict(task)
        suggestion["trigger_reasons"] = rule_reasons
        suggestion["deletion_reasoning"] = item.get("reason") or llm.generate_deletion_reasoning(
            task, rule_reasons
        )
        suggestions.append(suggestion)

    return suggestions


def _fallback_reasoning(
    selected_count: int, deferred_count: int, snapshot: Dict[str, Any], lang: str
) -> str:
    capacity = int(snapshot.get("capacity_units", 0) or 0)
    required = int(snapshot.get("required_units", 0) or 0)
    if lang == "zh":
        return (
            f"今天保留了 {selected_count} 项任务，推迟了 {deferred_count} 项。"
            f"当前容量为 {capacity}，需求约为 {required}。优先删减低承诺任务。"
        )
    return (
        f"Selected {selected_count} task(s), deferred {deferred_count}. "
        f"Capacity {capacity}, required {required}. Remove low-commitment tasks first."
    )


def _build_decision_summary(
    selected_count: int,
    deferred_count: int,
    delete_count: int,
    snapshot: Dict[str, Any],
    lang: str,
) -> Dict[str, Any]:
    overload = int(snapshot.get("overload_units", 0) or 0)
    capacity = int(snapshot.get("capacity_units", 0) or 0)
    required = int(snapshot.get("required_units", 0) or 0)

    if lang == "zh":
        if overload > 0:
            headline = f"今天只保留 {selected_count} 项，先释放过载。"
            tension = f"当前需求约 {required} 单位，但容量只有 {capacity}。"
            next_step = "先完成保留项，再决定是否恢复被推迟的任务。"
        else:
            headline = f"今天聚焦 {selected_count} 项，计划保持在容量内。"
            tension = f"{deferred_count} 项被推迟，{delete_count} 项值得重新审视。"
            next_step = "如果今天再次滑坡，明天应该继续缩小承诺。"
        return {
            "headline": headline,
            "tension": tension,
            "next_step": next_step,
            "keep_count": selected_count,
            "defer_count": deferred_count,
            "delete_count": delete_count,
            "capacity_units": capacity,
            "required_units": required,
        }

    if overload > 0:
        headline = f"Keep only {selected_count} task(s) today to relieve overload."
        tension = f"Demand is about {required} units while capacity is {capacity}."
        next_step = "Finish the kept work before restoring anything deferred."
    else:
        headline = f"Focus on {selected_count} task(s) today and protect the lighter plan."
        tension = (
            f"{deferred_count} task(s) were pushed out and {delete_count} deserve a second look."
        )
        next_step = "If today slips, shrink tomorrow's commitments instead of rolling everything forward."

    return {
        "headline": headline,
        "tension": tension,
        "next_step": next_step,
        "keep_count": selected_count,
        "defer_count": deferred_count,
        "delete_count": delete_count,
        "capacity_units": capacity,
        "required_units": required,
    }


def _build_coach_notes(
    snapshot: Dict[str, Any],
    deferred_tasks: List[Dict[str, Any]],
    deletion_suggestions: List[Dict[str, Any]],
    lang: str,
) -> List[str]:
    overload = int(snapshot.get("overload_units", 0) or 0)
    notes: List[str] = []

    if lang == "zh":
        if overload > 0:
            notes.append(f"当前任务总量超出容量约 {overload} 单位，今天不适合全部推进。")
        if deferred_tasks:
            titles = "、".join(task.get("title", "") for task in deferred_tasks[:3] if task.get("title"))
            if titles:
                notes.append(f"被推迟的任务包括：{titles}。")
        if deletion_suggestions:
            notes.append("至少有一项任务已经表现出低价值或低承诺信号，适合直接删除。")
        if not notes:
            notes.append("当前计划已经比较克制，重点是保护执行，而不是继续加任务。")
        return notes

    if overload > 0:
        notes.append(
            f"The active backlog exceeds capacity by about {overload} unit(s), so not everything deserves attention today."
        )
    if deferred_tasks:
        titles = ", ".join(task.get("title", "") for task in deferred_tasks[:3] if task.get("title"))
        if titles:
            notes.append(f"Deferred work now includes: {titles}.")
    if deletion_suggestions:
        notes.append(
            "At least one task is showing repeated low-commitment signals and should be questioned, not preserved by default."
        )
    if not notes:
        notes.append(
            "The current plan is already relatively constrained. Protect execution before adding anything else."
        )
    return notes


def generate_daily_plan(
    tasks,
    target_date: str,
    lang: str = "en",
    capacity_units: Optional[int] = None,
) -> Dict[str, Any]:
    """Generate one capacity-aware plan with explainable deletion recommendations."""

    task_dicts = [task.to_dict() for task in tasks]
    if not task_dicts:
        return {
            "selected_tasks": [],
            "deferred_tasks": [],
            "deletion_suggestions": [],
            "reasoning": "",
            "overload_warning": "",
            "max_tasks": 0,
            "classified_tasks": [],
            "capacity_summary": {
                "capacity_units": normalize_capacity_units(capacity_units),
                "required_units": 0,
                "selected_units": 0,
                "overload_units": 0,
            },
            "decision_summary": {},
            "coach_notes": [],
            "selected_task_ids": [],
            "deferred_task_ids": [],
        }

    snapshot = build_capacity_snapshot(task_dicts, capacity_units=capacity_units)
    llm = get_llm_service(lang=lang)
    ai_result = llm.recommend_decisions(
        {
            "target_date": target_date,
            "tasks": task_dicts,
            "rule_snapshot": snapshot,
            "lang": lang,
        }
    )

    all_task_ids = [int(task["id"]) for task in task_dicts]
    guarded = _apply_guardrails(ai_result, snapshot, all_task_ids)

    keep_ids = guarded["keep_ids"]
    defer_ids = guarded["defer_ids"]
    task_by_id = {int(task["id"]): task for task in task_dicts}

    selected_tasks = []
    for task_id in keep_ids:
        meta = snapshot["task_meta"].get(task_id, {})
        selected_tasks.append(
            {
                "task_id": task_id,
                "reason": "Protected by hard rule." if meta.get("non_negotiable") else "Fits current capacity.",
                "category": "core",
            }
        )

    deferred_tasks = [task_by_id[task_id] for task_id in defer_ids if task_id in task_by_id]

    deletion_suggestions = _build_deletion_suggestions(
        task_by_id=task_by_id,
        snapshot=snapshot,
        llm=llm,
        delete_items=guarded["delete_items"],
        selected_ids=keep_ids,
    )

    deletion_ids = {int(item["id"]) for item in deletion_suggestions}
    classified_tasks = []
    for task_id in all_task_ids:
        if task_id in deletion_ids:
            category = "deletion_candidate"
        elif task_id in keep_ids:
            category = "core"
        else:
            category = "deferrable"
        classified_tasks.append({"task_id": task_id, "category": category})

    reasoning = guarded["reasoning"] or _fallback_reasoning(
        selected_count=len(keep_ids),
        deferred_count=len(defer_ids),
        snapshot=snapshot,
        lang=lang,
    )

    return {
        "selected_tasks": selected_tasks,
        "deferred_tasks": deferred_tasks,
        "deletion_suggestions": deletion_suggestions,
        "reasoning": reasoning,
        "overload_warning": _build_overload_warning(snapshot, lang),
        "max_tasks": len(keep_ids),
        "classified_tasks": classified_tasks,
        "capacity_summary": {
            "capacity_units": snapshot["capacity_units"],
            "required_units": snapshot["required_units"],
            "selected_units": snapshot["selected_units"],
            "overload_units": snapshot["overload_units"],
        },
        "decision_summary": _build_decision_summary(
            selected_count=len(keep_ids),
            deferred_count=len(defer_ids),
            delete_count=len(deletion_suggestions),
            snapshot=snapshot,
            lang=lang,
        ),
        "coach_notes": _build_coach_notes(
            snapshot=snapshot,
            deferred_tasks=deferred_tasks,
            deletion_suggestions=deletion_suggestions,
            lang=lang,
        ),
        "selected_task_ids": keep_ids,
        "deferred_task_ids": defer_ids,
    }


def regenerate_reasoning(
    plan,
    all_active_tasks,
    lang: str = "en",
    capacity_units: Optional[int] = None,
) -> Dict[str, Any]:
    """Regenerate plan explanation without changing the selected tasks."""

    all_dicts = [task.to_dict() for task in all_active_tasks]
    snapshot = build_capacity_snapshot(all_dicts, capacity_units=capacity_units)

    selected_task_ids = {plan_task.task_id for plan_task in plan.plan_tasks}
    selected = [task for task in all_dicts if int(task["id"]) in selected_task_ids]
    deferred = [task for task in all_dicts if int(task["id"]) not in selected_task_ids]

    reasoning = plan.reasoning or _fallback_reasoning(
        selected_count=len(selected),
        deferred_count=len(deferred),
        snapshot=snapshot,
        lang=lang,
    )

    from core.llm.mock import MockLLMService

    mock_llm = MockLLMService(lang=lang)
    delete_items = [
        {"task_id": item["task_id"], "reason": ""}
        for item in snapshot.get("deletion_candidates", [])[:3]
    ]
    task_by_id = {int(task["id"]): task for task in all_dicts}
    deletion_suggestions = _build_deletion_suggestions(
        task_by_id=task_by_id,
        snapshot=snapshot,
        llm=mock_llm,
        delete_items=delete_items,
        selected_ids=list(selected_task_ids),
    )

    return {
        "reasoning": reasoning,
        "overload_warning": _build_overload_warning(snapshot, lang),
        "deletion_suggestions": deletion_suggestions,
        "capacity_summary": {
            "capacity_units": snapshot["capacity_units"],
            "required_units": snapshot["required_units"],
            "selected_units": snapshot["selected_units"],
            "overload_units": snapshot["overload_units"],
        },
        "decision_summary": _build_decision_summary(
            selected_count=len(selected),
            deferred_count=len(deferred),
            delete_count=len(deletion_suggestions),
            snapshot=snapshot,
            lang=lang,
        ),
        "coach_notes": _build_coach_notes(
            snapshot=snapshot,
            deferred_tasks=deferred,
            deletion_suggestions=deletion_suggestions,
            lang=lang,
        ),
        "deferred_tasks": deferred,
        "selected_task_ids": list(selected_task_ids),
        "deferred_task_ids": [int(task["id"]) for task in deferred],
    }


def build_replan_preview(
    tasks,
    target_date: str,
    lang: str = "en",
    base_capacity_units: Optional[int] = None,
    missed_count: int = 0,
    deferred_count: int = 0,
) -> Dict[str, Any]:
    """Build an adaptive next-step preview after the user reports outcomes."""

    base_capacity = normalize_capacity_units(base_capacity_units)
    penalty = 0
    if (missed_count + deferred_count) >= 2:
        penalty += 1
    if missed_count >= 2:
        penalty += 1

    adjusted_capacity = normalize_capacity_units(base_capacity - penalty)
    preview = generate_daily_plan(
        tasks,
        target_date=target_date,
        lang=lang,
        capacity_units=adjusted_capacity,
    )

    task_by_id = {int(task.id): task.to_dict() for task in tasks}
    preview["preview_tasks"] = [
        {
            "id": item["task_id"],
            "task_id": item["task_id"],
            "status": "planned",
            "reason": item.get("reason", ""),
            "task": task_by_id.get(int(item["task_id"])),
        }
        for item in preview.get("selected_tasks", [])
    ]

    if lang == "zh":
        adaptive_reason = (
            f"根据今天的结果，明天的建议容量调整为 {adjusted_capacity}。"
            if penalty > 0
            else f"根据今天的结果，明天先保持 {adjusted_capacity} 的容量。"
        )
    else:
        adaptive_reason = (
            f"Tomorrow's preview trims capacity to {adjusted_capacity} based on today's misses and deferrals."
            if penalty > 0
            else f"Tomorrow's preview keeps capacity at {adjusted_capacity} because today's load still looks stable."
        )

    preview["target_date"] = target_date
    preview["base_capacity_units"] = base_capacity
    preview["adjusted_capacity_units"] = adjusted_capacity
    preview["adaptive_reason"] = adaptive_reason
    preview["missed_count"] = missed_count
    preview["deferred_count"] = deferred_count
    return preview
