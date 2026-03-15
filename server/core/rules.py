"""Deterministic rule layer for capacity-aware deletion planning."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

DEFAULT_CAPACITY_UNITS = 6
MIN_CAPACITY_UNITS = 1
MAX_CAPACITY_UNITS = 24

DEFERRAL_DELETE_THRESHOLD = 3
LOW_COMPLETION_RATE = 0.3

URGENT_KEYWORDS = (
    "deadline",
    "urgent",
    "must",
    "submit",
    "exam",
    "client",
    "截止",
    "紧急",
    "必须",
    "提交",
    "考试",
    "客户",
    "今天",
    "马上",
    "立刻",
)


def normalize_capacity_units(capacity_units: Optional[int]) -> int:
    if capacity_units is None:
        return DEFAULT_CAPACITY_UNITS
    bounded = max(MIN_CAPACITY_UNITS, min(MAX_CAPACITY_UNITS, int(capacity_units)))
    return bounded


def estimate_effort_units(task: Dict[str, Any]) -> int:
    explicit_effort = task.get("effort_units")
    if isinstance(explicit_effort, int) and explicit_effort > 0:
        return min(8, explicit_effort)

    priority = int(task.get("priority", 0) or 0)
    text = f"{task.get('title', '')} {task.get('description', '')}".lower()

    effort = 1
    if priority >= 1:
        effort += 1
    if priority >= 3:
        effort += 1
    if priority >= 5:
        effort += 1
    if any(keyword in text for keyword in URGENT_KEYWORDS):
        effort += 1

    return min(8, effort)


def is_non_negotiable(task: Dict[str, Any]) -> bool:
    priority = int(task.get("priority", 0) or 0)
    category = task.get("category", "")
    text = f"{task.get('title', '')} {task.get('description', '')}".lower()
    return bool(
        category == "core"
        or priority >= 5
        or "must" in text
        or "必须" in text
        or "一定要" in text
    )


def keep_score(task: Dict[str, Any], effort_units: int, non_negotiable: bool) -> float:
    priority = int(task.get("priority", 0) or 0)
    deferral_count = int(task.get("deferral_count", 0) or 0)
    completion_count = int(task.get("completion_count", 0) or 0)
    text = f"{task.get('title', '')} {task.get('description', '')}".lower()

    score = float(priority * 2)
    if non_negotiable:
        score += 6.0
    if any(keyword in text for keyword in URGENT_KEYWORDS):
        score += 2.0
    score += min(2.0, completion_count * 0.5)
    score -= min(4.0, deferral_count * 1.2)
    score -= max(0, effort_units - 4) * 0.5

    due_date = task.get("due_date")
    if due_date:
        try:
            from datetime import date as date_cls
            from core.time import local_today

            days_left = (date_cls.fromisoformat(due_date) - local_today()).days
            if days_left <= 0:
                score += 8.0
            elif days_left <= 1:
                score += 5.0
            elif days_left <= 3:
                score += 3.0
            elif days_left <= 7:
                score += 1.0
        except (ValueError, TypeError):
            pass

    return round(score, 2)


def _rule_reasons_for_deletion(task: Dict[str, Any], deferred: bool) -> List[str]:
    reasons: List[str] = []
    deferral_count = int(task.get("deferral_count", 0) or 0)
    completion_count = int(task.get("completion_count", 0) or 0)
    attempts = deferral_count + completion_count

    if deferral_count >= DEFERRAL_DELETE_THRESHOLD:
        reasons.append(f"Deferred {deferral_count} times.")

    if attempts >= 3:
        completion_rate = completion_count / attempts if attempts else 0.0
        if completion_rate < LOW_COMPLETION_RATE:
            reasons.append(
                f"Low completion rate {completion_rate:.0%} ({completion_count}/{attempts})."
            )

    if deferred:
        reasons.append("Deferred by capacity constraints in the current plan.")

    return reasons


def localize_rule_reason(reason: str, lang: str = "en") -> str:
    if lang != "zh":
        return reason

    deferred_match = re.fullmatch(r"Deferred (\d+) times\.", reason)
    if deferred_match:
        return f'已被推迟 {deferred_match.group(1)} 次。'

    completion_match = re.fullmatch(
        r"Low completion rate (\d+%) \((\d+)/(\d+)\)\.", reason
    )
    if completion_match:
        rate, completed, attempts = completion_match.groups()
        return f"完成率偏低 {rate}（{completed}/{attempts}）。"

    if reason == "Deferred by capacity constraints in the current plan.":
        return "这一轮因为容量限制被推后。"

    return reason


def localize_rule_reasons(reasons: List[str], lang: str = "en") -> List[str]:
    return [localize_rule_reason(reason, lang) for reason in reasons]


def build_capacity_snapshot(
    tasks: List[Dict[str, Any]],
    capacity_units: Optional[int] = None,
) -> Dict[str, Any]:
    capacity = normalize_capacity_units(capacity_units)

    enriched: List[Dict[str, Any]] = []
    for task in tasks:
        effort_units = estimate_effort_units(task)
        non_negotiable = is_non_negotiable(task)
        score = keep_score(task, effort_units, non_negotiable)
        enriched.append(
            {
                "task": task,
                "task_id": int(task["id"]),
                "effort_units": effort_units,
                "non_negotiable": non_negotiable,
                "keep_score": score,
            }
        )

    enriched.sort(
        key=lambda item: (
            0 if item["non_negotiable"] else 1,
            -item["keep_score"],
            -int(item["task"].get("priority", 0) or 0),
            str(item["task"].get("created_at") or ""),
        )
    )

    selected_ids: List[int] = []
    deferred_ids: List[int] = []
    non_negotiable_ids: List[int] = []
    used_units = 0
    required_units = 0
    task_meta: Dict[int, Dict[str, Any]] = {}

    for item in enriched:
        task_id = item["task_id"]
        effort_units = item["effort_units"]
        required_units += effort_units

        if item["non_negotiable"]:
            non_negotiable_ids.append(task_id)

        can_fit = (used_units + effort_units) <= capacity
        if item["non_negotiable"] or can_fit:
            selected_ids.append(task_id)
            used_units += effort_units
        else:
            deferred_ids.append(task_id)

        task_meta[task_id] = {
            "effort_units": effort_units,
            "non_negotiable": item["non_negotiable"],
            "keep_score": item["keep_score"],
        }

    deletion_candidates: List[Dict[str, Any]] = []
    deferred_set = set(deferred_ids)
    for item in enriched:
        task = item["task"]
        task_id = item["task_id"]
        if item["non_negotiable"]:
            continue
        reasons = _rule_reasons_for_deletion(task, deferred=task_id in deferred_set)
        if not reasons:
            continue
        deletion_candidates.append(
            {
                "task_id": task_id,
                "rule_reasons": reasons,
                "effort_units": item["effort_units"],
                "keep_score": item["keep_score"],
            }
        )

    deletion_candidates.sort(
        key=lambda item: (
            -len(item["rule_reasons"]),
            item["keep_score"],
            -item["effort_units"],
        )
    )

    overload_units = max(0, required_units - capacity)
    hard_commitment_overload = max(0, used_units - capacity)

    return {
        "capacity_units": capacity,
        "required_units": required_units,
        "selected_units": used_units,
        "overload_units": overload_units,
        "hard_commitment_overload": hard_commitment_overload,
        "is_overloaded": overload_units > 0,
        "selected_task_ids": selected_ids,
        "deferred_task_ids": deferred_ids,
        "non_negotiable_task_ids": non_negotiable_ids,
        "deletion_candidates": deletion_candidates,
        "task_meta": task_meta,
    }
