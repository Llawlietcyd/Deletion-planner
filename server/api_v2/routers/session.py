"""Prototype session and onboarding endpoints for multi-user local workspaces."""

from __future__ import annotations

from datetime import date
import secrets
from typing import Any, Dict, Iterable, Tuple

from fastapi import APIRouter, HTTPException, Request

from api_v2.schemas import OnboardingCompleteRequest, SessionLoginRequest
from api_v2.user_context import (
    get_active_session,
    get_session_state,
    onboarding_key,
    plan_storage_key,
    read_setting,
    require_current_user,
    write_setting,
)
from core.planner import generate_daily_plan
from core.task_kind import has_explicit_weekly_recurrence, infer_recurrence_weekday, infer_task_kind
from database.db import get_db
from database.models import (
    DailyPlan,
    HistoryAction,
    PlanTask,
    PlanTaskStatus,
    Task,
    TaskCategory,
    TaskHistory,
    TaskStatus,
    User,
    UserSession,
)

router = APIRouter(tags=["session"])


def _normalize_birthday(raw: str | None) -> str | None:
    if not raw:
        return None

    value = raw.strip()
    if not value:
        return None

    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "INVALID_BIRTHDAY",
                "message": "Birthday must be a valid date in YYYY-MM-DD format",
            },
        ) from exc

    return parsed.isoformat()


def _parse_task_line(line: str) -> Tuple[str, int, str | None]:
    import re
    from datetime import timedelta

    priority = 0
    due_date = None
    text = line.strip()

    priority_map = {
        "!urgent": 5,
        "!紧急": 5,
        "!high": 3,
        "!高": 3,
        "!medium": 1,
        "!中": 1,
        "!low": 0,
        "!低": 0,
    }
    for marker, level in priority_map.items():
        if marker in text.lower():
            priority = level
            text = re.sub(re.escape(marker), "", text, flags=re.IGNORECASE).strip()
            break

    date_match = re.search(r"@(\d{4}-\d{2}-\d{2})", text)
    if date_match:
        due_date = date_match.group(1)
        text = f'{text[:date_match.start()].strip()} {text[date_match.end():].strip()}'.strip()
    elif "@today" in text.lower() or "@今天" in text:
        from core.time import local_today_iso
        due_date = local_today_iso()
        text = re.sub(r"@today|@今天", "", text, flags=re.IGNORECASE).strip()
    elif "@tomorrow" in text.lower() or "@明天" in text:
        from core.time import local_date_offset_iso
        due_date = local_date_offset_iso(1)
        text = re.sub(r"@tomorrow|@明天", "", text, flags=re.IGNORECASE).strip()

    return text.strip(), priority, due_date


def _iter_lines(raw: str) -> Iterable[str]:
    for line in raw.splitlines():
        cleaned = line.strip()
        if cleaned:
            yield cleaned


def _build_task_specs(payload: OnboardingCompleteRequest) -> Iterable[Dict[str, Any]]:
    for line in _iter_lines(payload.commitments):
        title, priority, _due_date = _parse_task_line(line)
        task_kind = infer_task_kind(title, "", None, None)
        if task_kind == "temporary" and infer_recurrence_weekday(title) is not None and not has_explicit_weekly_recurrence(title):
            task_kind = "weekly"
        elif task_kind == "temporary":
            task_kind = "daily"
        yield {
            "title": title,
            "priority": max(priority, 5),
            "due_date": None,
            "category": TaskCategory.CORE.value,
            "description": "",
            "task_kind": task_kind,
            "recurrence_weekday": infer_recurrence_weekday(title) if task_kind == "weekly" else None,
        }

    for line in _iter_lines(payload.goals):
        title, priority, due_date = _parse_task_line(line)
        yield {
            "title": title,
            "priority": max(priority, 3),
            "due_date": due_date,
            "category": TaskCategory.UNCLASSIFIED.value,
            "description": "",
            "task_kind": "temporary",
            "recurrence_weekday": None,
        }

    for line in _iter_lines(payload.brain_dump):
        title, priority, due_date = _parse_task_line(line)
        yield {
            "title": title,
            "priority": priority,
            "due_date": due_date,
            "category": TaskCategory.UNCLASSIFIED.value,
            "description": "",
            "task_kind": "temporary",
            "recurrence_weekday": None,
        }


def _localized_history_reason(key: str, lang: str) -> str:
    if lang == "zh":
        return {
            "onboarding_import": "任务由首次初始化导入。",
        }.get(key, "")
    return {
        "onboarding_import": "Task imported from onboarding.",
    }.get(key, "")


def _session_response(session: Dict[str, Any], onboarding: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "logged_in": bool(session.get("logged_in")),
        "display_name": session.get("display_name", ""),
        "user_id": session.get("user_id"),
        "has_password": bool(session.get("user_id")),
        "session_token": session.get("session_token", ""),
        "onboarding_completed": bool(onboarding.get("completed")),
        "daily_capacity": int(onboarding.get("daily_capacity", 6) or 6),
        "profile_summary": onboarding.get("profile_summary", ""),
    }


@router.get("/session")
def get_session(request: Request):
    with get_db() as db:
        session = get_session_state(db, request)
        onboarding = {"completed": False, "daily_capacity": 6, "profile_summary": ""}
        if session.get("user_id"):
            onboarding = read_setting(
                db,
                onboarding_key(int(session["user_id"])),
                onboarding,
            )
        return _session_response(session, onboarding)


@router.post("/session/login")
def login(payload: SessionLoginRequest):
    with get_db() as db:
        display_name = payload.display_name.strip()
        password = payload.password.strip()
        birthday = _normalize_birthday(payload.birthday)
        if not display_name:
            raise HTTPException(
                status_code=400,
                detail={"error_code": "INVALID_NAME", "message": "Display name is required"},
            )
        if not password:
            raise HTTPException(
                status_code=400,
                detail={"error_code": "INVALID_PASSWORD", "message": "Password is required"},
            )

        user = db.query(User).filter(User.username == display_name).first()
        if user and user.password != password:
            raise HTTPException(
                status_code=401,
                detail={"error_code": "INVALID_CREDENTIALS", "message": "Incorrect password"},
            )
        if not user:
            user = User(username=display_name, password=password)
            if birthday:
                user.birthday = birthday
            if payload.gender:
                user.gender = payload.gender
            db.add(user)
            db.flush()
        else:
            if birthday and not user.birthday:
                user.birthday = birthday
            if payload.gender and not user.gender:
                user.gender = payload.gender

        session_token = secrets.token_urlsafe(32)
        db.add(UserSession(user_id=user.id, token=session_token))
        db.flush()
        current = {
            "logged_in": True,
            "user_id": user.id,
            "display_name": user.username,
            "session_token": session_token,
        }
        onboarding = read_setting(
            db,
            onboarding_key(user.id),
            {"completed": False, "daily_capacity": 6, "profile_summary": ""},
        )
        return _session_response(current, onboarding)


@router.post("/session/logout")
def logout(request: Request):
    with get_db() as db:
        active_session = get_active_session(db, request)
        if active_session:
            db.delete(active_session)
            db.flush()
        current = {"logged_in": False, "user_id": None, "display_name": "", "session_token": ""}
        onboarding = {"completed": False, "daily_capacity": 6, "profile_summary": ""}
        return _session_response(current, onboarding)


@router.get("/onboarding")
def get_onboarding_state(request: Request):
    with get_db() as db:
        user = require_current_user(db, request)
        onboarding = read_setting(
            db,
            onboarding_key(user.id),
            {"completed": False, "daily_capacity": 6, "profile_summary": ""},
        )
        return onboarding


@router.post("/onboarding/complete", status_code=201)
def complete_onboarding(payload: OnboardingCompleteRequest, request: Request):
    from core.time import local_today_iso
    target_date = local_today_iso()

    with get_db() as db:
        user = require_current_user(db, request)
        session = get_session_state(db, request)

        if payload.reset_existing:
            user_tasks = db.query(Task).filter(Task.user_id == user.id).all()
            user_task_ids = [task.id for task in user_tasks]
            user_plans = db.query(DailyPlan).filter(DailyPlan.date.like(f"{user.id}:%")).all()
            user_plan_ids = [plan.id for plan in user_plans]
            if user_task_ids:
                db.query(TaskHistory).filter(TaskHistory.task_id.in_(user_task_ids)).delete(synchronize_session=False)
            if user_plan_ids:
                db.query(PlanTask).filter(PlanTask.plan_id.in_(user_plan_ids)).delete(synchronize_session=False)
                db.query(DailyPlan).filter(DailyPlan.id.in_(user_plan_ids)).delete(synchronize_session=False)
            db.query(Task).filter(Task.user_id == user.id).delete(synchronize_session=False)
            db.flush()

        created_tasks = []
        for spec in _build_task_specs(payload):
            if not spec["title"]:
                continue
            task = Task(
                user_id=user.id,
                title=spec["title"],
                description=spec["description"],
                priority=spec["priority"],
                category=spec["category"],
                due_date=spec["due_date"],
                task_kind=spec.get("task_kind", "temporary"),
                recurrence_weekday=spec.get("recurrence_weekday"),
                status=TaskStatus.ACTIVE.value,
                source="manual",
                decision_reason="Imported during onboarding.",
            )
            db.add(task)
            db.flush()
            db.add(
                TaskHistory(
                    task_id=task.id,
                    date=target_date,
                    action=HistoryAction.CREATED.value,
                    ai_reasoning=_localized_history_reason("onboarding_import", payload.lang),
                )
            )
            created_tasks.append(task)

        if not created_tasks:
            raise HTTPException(
                status_code=400,
                detail={"error_code": "EMPTY_ONBOARDING", "message": "Add at least one task or commitment"},
            )

        plan_result = generate_daily_plan(
            created_tasks,
            target_date=target_date,
            lang=payload.lang,
            capacity_units=payload.daily_capacity,
        )

        category_by_id = {
            item["task_id"]: item.get("category", TaskCategory.UNCLASSIFIED.value)
            for item in plan_result.get("classified_tasks", [])
        }
        for task in created_tasks:
            if task.id in category_by_id:
                task.category = category_by_id[task.id]
                task.source = "ai"
                task.decision_reason = "Category inferred during onboarding."

        daily_plan = DailyPlan(
            date=plan_storage_key(user.id, target_date),
            reasoning=plan_result.get("reasoning", ""),
            overload_warning=plan_result.get("overload_warning", ""),
            max_tasks=plan_result.get("max_tasks", 4),
        )
        db.add(daily_plan)
        db.flush()

        for index, selected in enumerate(plan_result.get("selected_tasks", [])):
            db.add(
                PlanTask(
                    plan_id=daily_plan.id,
                    task_id=selected["task_id"],
                    status=PlanTaskStatus.PLANNED.value,
                    order=index,
                )
            )
            db.add(
                TaskHistory(
                    task_id=selected["task_id"],
                    date=target_date,
                    action=HistoryAction.PLANNED.value,
                    ai_reasoning=selected.get("reason", ""),
                )
            )

        onboarding = {
            "completed": True,
            "daily_capacity": payload.daily_capacity,
            "profile_summary": (
                f'{session.get("display_name", "User")} imported {len(created_tasks)} task(s) '
                "during onboarding."
            ),
            "brain_dump": payload.brain_dump,
            "commitments": payload.commitments,
            "goals": payload.goals,
        }
        write_setting(db, onboarding_key(user.id), onboarding)
        db.flush()

        persisted_plan = db.get(DailyPlan, daily_plan.id)
        result = persisted_plan.to_dict(include_tasks=True)
        result["deletion_suggestions"] = plan_result.get("deletion_suggestions", [])
        result["deferred_tasks"] = plan_result.get("deferred_tasks", [])
        result["capacity_summary"] = plan_result.get("capacity_summary", {})
        result["decision_summary"] = plan_result.get("decision_summary", {})
        result["coach_notes"] = plan_result.get("coach_notes", [])
        result["selected_task_ids"] = plan_result.get("selected_task_ids", [])
        result["deferred_task_ids"] = plan_result.get("deferred_task_ids", [])
        return {
            "session": _session_response(session, onboarding),
            "created_task_count": len(created_tasks),
            "plan": result,
        }
