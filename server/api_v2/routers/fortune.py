"""Daily fortune / tarot endpoints with plan, mood, and zodiac context."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from api_v2.user_context import plan_storage_key, require_current_user
from core.llm import get_llm_service
from core.tarot_catalog import enrich_fortune_card
from core.time import local_today_iso
from database.db import get_db
from database.models import DailyFortune, DailyPlan, MoodEntry, PlanTaskStatus, Task, TaskStatus

router = APIRouter(tags=["fortune"])


def _get_zodiac(birthday: str) -> dict:
    """Derive Western + Chinese zodiac from birthday string YYYY-MM-DD."""
    if not birthday:
        return {
            "western": "Unknown",
            "western_zh": "未知星座",
            "chinese": "Unknown",
            "chinese_zh": "未知生肖",
            "has_birthday": False,
        }
    try:
        parts = birthday.split("-")
        month, day = int(parts[1]), int(parts[2])
        year = int(parts[0])
    except (IndexError, ValueError):
        return {
            "western": "Unknown",
            "western_zh": "未知星座",
            "chinese": "Unknown",
            "chinese_zh": "未知生肖",
            "has_birthday": False,
        }

    # Western zodiac
    western_signs = [
        ((1, 20), "Aquarius", "水瓶座"), ((2, 19), "Pisces", "双鱼座"),
        ((3, 21), "Aries", "白羊座"), ((4, 20), "Taurus", "金牛座"),
        ((5, 21), "Gemini", "双子座"), ((6, 21), "Cancer", "巨蟹座"),
        ((7, 23), "Leo", "狮子座"), ((8, 23), "Virgo", "处女座"),
        ((9, 23), "Libra", "天秤座"), ((10, 23), "Scorpio", "天蝎座"),
        ((11, 22), "Sagittarius", "射手座"), ((12, 22), "Capricorn", "摩羯座"),
    ]
    western, western_zh = "Capricorn", "摩羯座"
    for (m, d), sign_en, sign_zh in western_signs:
        if (month, day) >= (m, d):
            western, western_zh = sign_en, sign_zh

    # Chinese zodiac
    animals_en = ["Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake",
                  "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]
    animals_zh = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]
    idx = (year - 1900) % 12
    chinese = animals_en[idx]
    chinese_zh = animals_zh[idx]

    return {
        "western": western,
        "western_zh": western_zh,
        "chinese": chinese,
        "chinese_zh": chinese_zh,
        "has_birthday": True,
    }


def _get_user_context(db, user) -> dict:
    """Gather plan/task/mood context for fortune generation."""
    today = local_today_iso()
    storage_key = plan_storage_key(user.id, today)

    plan = db.query(DailyPlan).filter(DailyPlan.date == storage_key).first()
    planned_tasks = []
    if plan:
        for plan_task in sorted(plan.plan_tasks, key=lambda item: item.order):
            task = plan_task.task
            if not task:
                continue
            if plan_task.status != PlanTaskStatus.PLANNED.value:
                continue
            if task.status != TaskStatus.ACTIVE.value:
                continue
            planned_tasks.append(task)

    # Active tasks
    tasks = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.status == TaskStatus.ACTIVE.value)
        .order_by(Task.priority.desc())
        .limit(10)
        .all()
    )
    if planned_tasks:
        task_summaries = [f"- {t.title} (priority {t.priority})" for t in planned_tasks[:5]]
    else:
        task_summaries = [f"- {t.title} (priority {t.priority})" for t in tasks[:5]]

    # Today's mood
    mood = (
        db.query(MoodEntry)
        .filter(MoodEntry.user_id == user.id, MoodEntry.date == today)
        .first()
    )

    return {
        "task_count": len(tasks),
        "planned_task_count": len(planned_tasks),
        "top_tasks": "\n".join(task_summaries[:5]) if task_summaries else "No tasks yet",
        "planned_tasks": [task.title for task in planned_tasks[:5]],
        "focus_task": planned_tasks[0].title if planned_tasks else (tasks[0].title if tasks else ""),
        "mood_level": mood.mood_level if mood else None,
        "mood_note": mood.note if mood else "",
    }


def _fortune_needs_refresh(data: dict, lang: str | None = None) -> bool:
    if not isinstance(data, dict):
        return True
    required_keys = ("focus_task", "planned_tasks", "visual_theme", "zodiac", "lang", "card_image_url", "card_imagery", "card_keywords")
    if any(key not in data for key in required_keys):
        return True
    if lang and data.get("lang") != lang:
        return True
    return False


@router.post("/fortune/daily")
def generate_daily_fortune(request: Request, lang: str = "en", force: bool = False):
    today = local_today_iso()
    with get_db() as db:
        user = require_current_user(db, request)

        # Check cache first
        existing = (
            db.query(DailyFortune)
            .filter(DailyFortune.user_id == user.id, DailyFortune.date == today)
            .first()
        )
        if existing:
            existing_data = json.loads(existing.fortune_data)
            if not force and not _fortune_needs_refresh(existing_data, lang):
                cached = enrich_fortune_card(existing_data, lang)
                cached["zodiac"] = existing_data.get("zodiac", {})
                cached["lang"] = lang
                existing.fortune_data = json.dumps(cached, ensure_ascii=False)
                db.flush()
                return cached

        birthday = user.birthday or ""
        zodiac = _get_zodiac(birthday)
        user_context = _get_user_context(db, user)

        llm = get_llm_service(lang=lang)
        fortune = llm.generate_fortune(
            birthday, today, lang=lang,
            zodiac=zodiac, user_context=user_context,
        )

        if not fortune:
            raise HTTPException(
                status_code=500,
                detail={"error_code": "FORTUNE_FAILED", "message": "Could not generate fortune"},
            )

        # Attach zodiac info
        fortune = enrich_fortune_card(fortune, lang)
        fortune["zodiac"] = zodiac
        fortune["lang"] = lang

        if existing:
            existing.fortune_data = json.dumps(fortune, ensure_ascii=False)
        else:
            entry = DailyFortune(
                user_id=user.id,
                date=today,
                fortune_data=json.dumps(fortune, ensure_ascii=False),
            )
            db.add(entry)
        db.flush()

        return fortune


@router.get("/fortune/today")
def get_today_fortune(request: Request, lang: str = "en"):
    today = local_today_iso()
    with get_db() as db:
        user = require_current_user(db, request)
        existing = (
            db.query(DailyFortune)
            .filter(DailyFortune.user_id == user.id, DailyFortune.date == today)
            .first()
        )
        if not existing:
            return {"generated": False}

        data = json.loads(existing.fortune_data)
        if _fortune_needs_refresh(data, lang):
            return {"generated": False}
        data = enrich_fortune_card(data, lang)
        data["generated"] = True
        data["lang"] = lang
        existing.fortune_data = json.dumps({k: v for k, v in data.items() if k != "generated"}, ensure_ascii=False)
        db.flush()
        return data
