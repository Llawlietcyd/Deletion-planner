"""Song recommendation endpoints."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import logging
import threading
import time

from fastapi import APIRouter, Request

from api_v2.user_context import plan_storage_key, require_current_user
from core.llm import get_llm_service
from core.spotify import enrich_song
from core.time import local_today_iso
from database.db import get_db
from database.models import DailyPlan, MoodEntry, PlanTaskStatus, Task, TaskStatus

router = APIRouter(tags=["songs"])
logger = logging.getLogger(__name__)
_RECOMMENDATION_CACHE_TTL_SECONDS = 60 * 10
_recommendation_cache: dict[str, tuple[float, dict]] = {}
_recommendation_cache_lock = threading.Lock()
_RECENT_SONG_HISTORY_TTL_SECONDS = 60 * 60 * 3
_recent_song_history: dict[int, tuple[float, list[dict[str, str]]]] = {}
_recent_song_history_lock = threading.Lock()


def _enrich_songs(songs):
    if len(songs) <= 1:
        return [enrich_song(song) for song in songs]

    max_workers = min(4, len(songs))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(enrich_song, songs))


def _cache_key(
    user_id: int,
    lang: str,
    mood_level: int,
    task_count: int,
    mood_note: str,
    recommendation_context: str,
) -> str:
    raw = " | ".join(
        [
            str(user_id),
            lang,
            str(mood_level),
            str(task_count),
            mood_note.strip(),
            recommendation_context.strip(),
        ]
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _get_cached_recommendations(cache_key: str):
    now = time.time()
    with _recommendation_cache_lock:
        entry = _recommendation_cache.get(cache_key)
        if not entry:
            return None
        expires_at, payload = entry
        if expires_at <= now:
            _recommendation_cache.pop(cache_key, None)
            return None
        return {
            **payload,
            "songs": [dict(song) for song in payload.get("songs", [])],
            "top_tasks": list(payload.get("top_tasks", [])),
        }


def _set_cached_recommendations(cache_key: str, payload: dict):
    with _recommendation_cache_lock:
        _recommendation_cache[cache_key] = (
            time.time() + _RECOMMENDATION_CACHE_TTL_SECONDS,
            {
                **payload,
                "songs": [dict(song) for song in payload.get("songs", [])],
                "top_tasks": list(payload.get("top_tasks", [])),
            },
        )


def _song_signature(song: dict) -> str:
    return f'{song.get("name", "").strip().casefold()} — {song.get("artist", "").strip().casefold()}'


def _song_label(song: dict) -> str:
    name = song.get("name", "").strip()
    artist = song.get("artist", "").strip()
    return f"{name} — {artist}" if artist else name


def _get_recent_song_history(user_id: int) -> list[dict[str, str]]:
    now = time.time()
    with _recent_song_history_lock:
        entry = _recent_song_history.get(user_id)
        if not entry:
            return []
        expires_at, songs = entry
        if expires_at <= now:
            _recent_song_history.pop(user_id, None)
            return []
        return [dict(song) for song in songs]


def _remember_recent_songs(user_id: int, songs: list[dict]) -> None:
    existing = _get_recent_song_history(user_id)
    history = []
    seen = set()
    for song in songs + existing:
        signature = song.get("signature") or _song_signature(song)
        if not signature or signature in seen:
            continue
        seen.add(signature)
        history.append(
            {
                "signature": signature,
                "label": song.get("label") or _song_label(song),
            }
        )
        if len(history) >= 24:
            break
    with _recent_song_history_lock:
        _recent_song_history[user_id] = (time.time() + _RECENT_SONG_HISTORY_TTL_SECONDS, history)


def _select_fresher_songs(user_id: int, songs: list[dict], limit: int = 8) -> list[dict]:
    recent = _get_recent_song_history(user_id)
    recent_signatures = {item.get("signature", "") for item in recent}
    selected = []
    deferred = []
    seen = set()

    for song in songs:
        signature = _song_signature(song)
        if not signature or signature in seen:
            continue
        seen.add(signature)
        target = deferred if signature in recent_signatures else selected
        target.append(song)

    chosen = (selected + deferred)[:limit]
    _remember_recent_songs(user_id, chosen)
    return chosen


def _planned_task_summary(db, user, today: str) -> str:
    storage_key = plan_storage_key(user.id, today)
    plan = db.query(DailyPlan).filter(DailyPlan.date == storage_key).first()
    if not plan:
        return ""

    lines = []
    for plan_task in sorted(plan.plan_tasks, key=lambda item: item.order):
        task = plan_task.task
        if not task:
            continue
        if plan_task.status != PlanTaskStatus.PLANNED.value:
            continue
        if task.status != TaskStatus.ACTIVE.value:
            continue
        lines.append(f"- {task.title}")
    return "\n".join(lines[:4])


def _infer_recommendation_strategy(mood_level: int, focus_task: str, high_priority_count: int) -> str:
    focus = (focus_task or "").lower()
    deep_focus_keywords = ("write", "draft", "study", "read", "code", "analy", "论文", "写", "读", "整理", "实验", "代码")
    social_keywords = ("call", "meeting", "interview", "present", "demo", "汇报", "面试", "答辩", "演示")
    admin_keywords = ("email", "reply", "organize", "admin", "回复", "安排", "整理")

    if any(keyword in focus for keyword in deep_focus_keywords):
        task_mode = "deep-focus"
    elif any(keyword in focus for keyword in social_keywords):
        task_mode = "confidence-social"
    elif any(keyword in focus for keyword in admin_keywords):
        task_mode = "light-admin"
    else:
        task_mode = "general-momentum"

    if mood_level <= 2 and task_mode == "deep-focus":
        return "gentle grounding focus"
    if mood_level <= 2:
        return "emotional regulation with low stimulation"
    if mood_level == 3 and high_priority_count >= 2:
        return "steady concentration without emotional spikes"
    if mood_level >= 4 and task_mode == "confidence-social":
        return "confident high-energy lift"
    if mood_level >= 4 and high_priority_count >= 1:
        return "momentum for meaningful execution"
    return "balanced focus"


def _song_context_summary(db, user, today: str, mood_level: int) -> tuple[list[str], str, str, str]:
    storage_key = plan_storage_key(user.id, today)
    plan = db.query(DailyPlan).filter(DailyPlan.date == storage_key).first()
    active_tasks = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.status == TaskStatus.ACTIVE.value)
        .order_by(Task.priority.desc(), Task.created_at.asc())
        .limit(8)
        .all()
    )

    planned = []
    focus_task = ""
    if plan:
        for plan_task in sorted(plan.plan_tasks, key=lambda item: item.order):
            task = plan_task.task
            if not task:
                continue
            if plan_task.status != PlanTaskStatus.PLANNED.value:
                continue
            if task.status != TaskStatus.ACTIVE.value:
                continue
            planned.append(task)
        if planned:
            focus_task = planned[0].title

    high_priority_count = (
        db.query(Task)
        .filter(
            Task.user_id == user.id,
            Task.status == TaskStatus.ACTIVE.value,
            Task.priority >= 4,
        )
        .count()
    )
    visible_tasks = planned[:5] if planned else active_tasks[:5]
    if not focus_task and visible_tasks:
        focus_task = visible_tasks[0].title
    top_titles = [task.title for task in visible_tasks[:4]]
    strategy = _infer_recommendation_strategy(mood_level, focus_task, high_priority_count)
    summary_lines = []
    if focus_task:
        summary_lines.append(f"Focus task: {focus_task}")
    if visible_tasks:
        summary_lines.append("Relevant tasks right now:")
        summary_lines.extend(f"- {task.title} (priority {task.priority})" for task in visible_tasks)
    summary_lines.append(f"High-priority active task count: {high_priority_count}")
    summary_lines.append(f"Recommendation strategy: {strategy}")
    return top_titles, focus_task, strategy, "\n".join(summary_lines)


@router.get("/songs/recommend")
def recommend_songs(request: Request, lang: str = "en", refresh_token: str = ""):
    today = local_today_iso()
    with get_db() as db:
        user = require_current_user(db, request)

        # Get today's mood
        mood_entry = (
            db.query(MoodEntry)
            .filter(MoodEntry.user_id == user.id, MoodEntry.date == today)
            .first()
        )
        mood_level = mood_entry.mood_level if mood_entry else 3  # default neutral

        # Get active task count
        task_count = (
            db.query(Task)
            .filter(Task.user_id == user.id, Task.status == TaskStatus.ACTIVE.value)
            .count()
        )
        mood_note = mood_entry.note if mood_entry else ""
        top_tasks, focus_task, recommendation_strategy, recommendation_context = _song_context_summary(
            db, user, today, mood_level
        )
        recommendation_cache_key = _cache_key(
            user.id,
            lang,
            mood_level,
            task_count,
            mood_note,
            recommendation_context,
        )

        llm = get_llm_service(lang=lang)
        normalized_refresh_token = refresh_token.strip()
        should_bypass_cache = bool(
            normalized_refresh_token and normalized_refresh_token.lower() not in {"0", "false", "none"}
        )
        cached_payload = None if should_bypass_cache else _get_cached_recommendations(recommendation_cache_key)
        cache_hit = cached_payload is not None
        llm_duration_ms = 0.0
        if cached_payload is not None:
            logger.info(
                "song_recommendation user_id=%s cache_hit=%s llm_ms=%.2f enrich_ms=%.2f song_count=%s",
                user.id,
                cache_hit,
                llm_duration_ms,
                0.0,
                len(cached_payload.get("songs", [])),
            )
            return cached_payload

        if cached_payload is None:
            recent_labels = [item.get("label", "") for item in _get_recent_song_history(user.id)[:12]]
            llm_started_at = time.perf_counter()
            songs = llm.recommend_songs(
                mood_level,
                task_count,
                lang=lang,
                mood_note=mood_note,
                top_tasks=recommendation_context,
                refresh_token=refresh_token or "initial-load",
                exclude_songs=recent_labels,
            )
            llm_duration_ms = (time.perf_counter() - llm_started_at) * 1000

        songs = _select_fresher_songs(user.id, songs, limit=8)

        enrich_started_at = time.perf_counter()
        songs = _enrich_songs(songs)
        enrich_duration_ms = (time.perf_counter() - enrich_started_at) * 1000

        payload = {
            "mood_level": mood_level,
            "task_count": task_count,
            "top_tasks": top_tasks,
            "focus_task": focus_task,
            "strategy": recommendation_strategy,
            "songs": songs,
        }

        if not should_bypass_cache:
            _set_cached_recommendations(recommendation_cache_key, payload)

        logger.info(
            "song_recommendation user_id=%s cache_hit=%s llm_ms=%.2f enrich_ms=%.2f song_count=%s",
            user.id,
            cache_hit,
            llm_duration_ms,
            enrich_duration_ms,
            len(songs),
        )

        return payload
