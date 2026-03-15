"""User concierge chatbox powered by DeepSeek with controlled write actions."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Request

from api_v2.schemas import AssistantChatRequest
from api_v2.user_context import plan_storage_key, read_setting, require_current_user, write_setting
from core.llm import get_llm_service
from core.planner import generate_daily_plan
from core.task_kind import WEEKDAY_PATTERNS, infer_recurrence_weekday, infer_relative_due_date, infer_task_kind, strip_task_kind_markers
from core.time import (
    local_date_offset_iso,
    local_today,
    local_today_iso,
    normalize_date_string,
    next_month_iso,
    next_week_iso,
    next_weekday_iso,
    upcoming_weekday_iso,
    upcoming_weekend_iso,
)
from database.db import get_db
from database.models import (
    DailyPlan,
    FocusSession,
    HistoryAction,
    MoodEntry,
    PlanTask,
    PlanTaskStatus,
    Task,
    TaskHistory,
    TaskStatus,
    User,
)

router = APIRouter(prefix="/assistant", tags=["assistant"])

PROFILE_KEY_PREFIX = "assistant_profile"
HISTORY_KEY_PREFIX = "assistant_history"
PENDING_KEY_PREFIX = "assistant_pending"

DEFAULT_PROFILE = {"completed": True, "next_question_index": 5, "answers": {}, "summary": ""}
DEFAULT_HISTORY = {"messages": []}
DEFAULT_PENDING = {"type": "", "data": {}}

PROFILE_QUESTIONS = [
    {
        "id": "main_focus",
        "en": "Before I start helping, what are the main things you're trying to move forward recently?",
        "zh": "在我开始帮你之前，你最近最想推进的几件事是什么？",
    },
    {
        "id": "protected_commitments",
        "en": "What commitments or routines should I protect instead of casually moving around?",
        "zh": "有哪些固定承诺或日常节奏是我应该优先保护、不能随便改动的？",
    },
    {
        "id": "planning_pain",
        "en": "What usually goes wrong in your planning now: too much, too vague, too easy to procrastinate, or something else?",
        "zh": "你现在排计划最容易出问题的点是什么：太多、太模糊、太容易拖延，还是别的？",
    },
    {
        "id": "energy_pattern",
        "en": "When are you usually sharp, and when do you tend to lose energy?",
        "zh": "你通常什么时候状态最好？什么时候容易掉电？",
    },
    {
        "id": "assistant_style",
        "en": "Do you want me to be more direct, more gentle, or somewhere in between when I suggest changes?",
        "zh": "当我建议你调整计划时，你更希望我是直接一点、温和一点，还是折中一点？",
    },
]


def _suggested_prompts(lang: str, profile_completed: bool, pending: Dict[str, Any]) -> List[str]:
    if pending.get("type") == "task_choice":
        return ["回复 1", "回复 2", "说得更具体一点"] if lang == "zh" else ["Reply 1", "Reply 2", "Be more specific"]
    if pending.get("type") == "llm_followup":
        return (
            ["更具体一点", "我指的是现有任务", "先别改，分析一下"]
            if lang == "zh"
            else ["Be more specific", "I mean an existing task", "Don't change anything, just analyze"]
        )
    return (
        [
            "我要吃饭",
            "把 exam 标成临时任务",
            "分析一下我最近的专注和完成情况",
            "我的生日是什么时候",
        ]
        if lang == "zh"
        else [
            "I need to eat lunch",
            "Mark exam as temporary",
            "Analyze my recent focus and completion pattern",
            "When is my birthday",
        ]
    )


def _assistant_status(profile: Dict[str, Any], pending: Dict[str, Any], lang: str) -> Dict[str, str]:
    if pending.get("type") == "task_choice":
        return {
            "phase": "pending",
            "label": "等待确认" if lang == "zh" else "Need confirmation",
            "hint": "回复编号，或者把任务名说得更完整。" if lang == "zh" else "Reply with a number or a clearer task name.",
        }
    if pending.get("type") == "llm_followup":
        return {
            "phase": "pending",
            "label": "需要补充" if lang == "zh" else "Need detail",
            "hint": pending.get("data", {}).get("question") or ("补一句更具体的信息。" if lang == "zh" else "Add one more detail."),
        }
    return {
        "phase": "ready",
        "label": "可直接执行" if lang == "zh" else "Ready to act",
        "hint": "你可以直接改任务，也可以普通问答；我不会默认乱改东西。" if lang == "zh" else "You can ask normal questions or request changes. I won't modify anything unless you ask.",
    }


def _profile_key(user_id: int) -> str:
    return f"{PROFILE_KEY_PREFIX}:{user_id}"


def _history_key(user_id: int) -> str:
    return f"{HISTORY_KEY_PREFIX}:{user_id}"


def _pending_key(user_id: int) -> str:
    return f"{PENDING_KEY_PREFIX}:{user_id}"


def _coerce_profile(profile: Dict[str, Any] | None) -> Dict[str, Any]:
    normalized = dict(DEFAULT_PROFILE)
    if isinstance(profile, dict):
        normalized.update(profile)
    if not normalized.get("completed"):
        normalized["completed"] = True
        normalized["next_question_index"] = len(PROFILE_QUESTIONS)
        answers = normalized.get("answers", {}) or {}
        if not normalized.get("summary") and answers:
            normalized["summary"] = " | ".join(
                f'{item["id"]}: {answers.get(item["id"], "")}' for item in PROFILE_QUESTIONS if answers.get(item["id"], "")
            )
    return normalized


def _push_message(history: Dict[str, Any], role: str, content: str) -> Dict[str, Any]:
    messages = list(history.get("messages", []))
    messages.append(
        {
            "id": f"{role}-{datetime.now(timezone.utc).timestamp()}",
            "role": role,
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    history["messages"] = messages[-24:]
    return history


def _question_text(index: int, lang: str) -> str:
    question = PROFILE_QUESTIONS[min(index, len(PROFILE_QUESTIONS) - 1)]
    return question["zh"] if lang == "zh" else question["en"]


def _ensure_profile_prompt(profile: Dict[str, Any], history: Dict[str, Any], lang: str) -> Dict[str, Any]:
    if history.get("messages"):
        return history
    opener = (
        "我是你在这个网站里的私人管家。你现在既可以让我加任务、删任务、改任务，也可以直接普通问答，比如问我你的任务、专注数据、生日日期；如果你的说法太模糊，我会追问。"
        if lang == "zh"
        else "I'm your private concierge inside this app. You can ask me to change tasks, or just ask normal questions about your data and the app. If something is too fuzzy, I'll ask one follow-up."
    )
    history = _push_message(history, "assistant", opener)
    return history


def _assistant_state(profile: Dict[str, Any], history: Dict[str, Any], pending: Dict[str, Any], lang: str) -> Dict[str, Any]:
    status = _assistant_status(profile, pending, lang)
    return {
        "profile_completed": bool(profile.get("completed")),
        "profile_summary": profile.get("summary", ""),
        "messages": history.get("messages", []),
        "pending": pending,
        "phase": status["phase"],
        "status_label": status["label"],
        "input_hint": status["hint"],
        "suggested_prompts": _suggested_prompts(lang, bool(profile.get("completed")), pending),
    }


def _user_context(db, user) -> Dict[str, Any]:
    user_obj = user if hasattr(user, "id") else db.get(User, int(user))
    user_id = user_obj.id
    today = local_today_iso()
    active_tasks = (
        db.query(Task)
        .filter(Task.user_id == user_id, Task.status == TaskStatus.ACTIVE.value)
        .order_by(Task.priority.desc(), Task.sort_order.asc(), Task.created_at.desc())
        .all()
    )
    plan = db.query(DailyPlan).filter(DailyPlan.date == plan_storage_key(user_id, today)).first()
    plan_tasks: List[Task] = []
    if plan:
        for plan_task in sorted(plan.plan_tasks, key=lambda item: item.order):
            if plan_task.status == PlanTaskStatus.PLANNED.value and plan_task.task and plan_task.task.status == TaskStatus.ACTIVE.value:
                plan_tasks.append(plan_task.task)
    mood = (
        db.query(MoodEntry)
        .filter(MoodEntry.user_id == user_id, MoodEntry.date == today)
        .order_by(MoodEntry.created_at.desc())
        .first()
    )
    focus_today = (
        db.query(FocusSession)
        .filter(FocusSession.user_id == user_id, FocusSession.date == today)
        .all()
    )
    completed_total = db.query(Task).filter(Task.user_id == user_id, Task.status == TaskStatus.COMPLETED.value).count()
    return {
        "today": today,
        "active_tasks": active_tasks,
        "plan_tasks": plan_tasks,
        "mood": mood,
        "focus_today_minutes": sum(item.duration_minutes for item in focus_today),
        "focus_today_sessions": len(focus_today),
        "completed_total": completed_total,
        "display_name": user_obj.username,
        "birthday": user_obj.birthday or "",
    }


def _task_titles(tasks: List[Task]) -> str:
    if not tasks:
        return "(none)"
    return "\n".join(f"- {task.title}" for task in tasks[:12])


def _list_tasks_reply(ctx: Dict[str, Any], lang: str) -> Dict[str, Any]:
    active_tasks = _visible_tasks(ctx.get("active_tasks", []) or [])
    plan_tasks = _visible_tasks(ctx.get("plan_tasks", []) or [])

    if not active_tasks:
        return {
            "reply": "你现在还没有活跃任务。" if lang == "zh" else "You don't have any active tasks right now.",
            "requires_clarification": False,
            "clarification_question": "",
            "actions": [],
        }

    if lang == "zh":
        active_line = "你当前的活跃任务有："
        active_items = " ".join(f"{index + 1}. {task.title}" for index, task in enumerate(active_tasks[:8]))
        if plan_tasks:
            planned_titles = "、".join(task.title for task in plan_tasks[:5])
            planned_line = f"今天放在列表里的是：{planned_titles}。"
        else:
            planned_line = "今天还没有单独标出来的计划子集。"
        reply = f"{active_line} {active_items}。{planned_line}"
    else:
        active_line = "Your active tasks are:"
        active_items = " ".join(f"{index + 1}. {task.title}" for index, task in enumerate(active_tasks[:8]))
        if plan_tasks:
            planned_titles = ", ".join(task.title for task in plan_tasks[:5])
            planned_line = f"Currently on today's list: {planned_titles}."
        else:
            planned_line = "There isn't a separate today subset right now."
        reply = f"{active_line} {active_items}. {planned_line}"

    return {
        "reply": reply,
        "requires_clarification": False,
        "clarification_question": "",
        "actions": [],
    }


def _analysis_reply(ctx: Dict[str, Any], lang: str) -> Dict[str, Any]:
    active_count = len(_visible_tasks(ctx.get("active_tasks", []) or []))
    focus_sessions = int(ctx.get("focus_today_sessions", 0) or 0)
    focus_minutes = int(ctx.get("focus_today_minutes", 0) or 0)
    completed_total = int(ctx.get("completed_total", 0) or 0)
    mood = ctx.get("mood")

    if lang == "zh":
        parts = [
            f"你现在有 {active_count} 个活跃任务。",
            f"今天记录了 {focus_sessions} 次专注，共 {focus_minutes} 分钟。",
            f"累计完成任务 {completed_total} 个。",
        ]
        if mood:
            parts.append(f"最新心情是 {mood.mood_level}/5。")
        if focus_sessions == 0 and completed_total == 0:
            parts.append("现在更像是刚起步状态，先完成一件小事或开一轮专注，我才能更准确地看出模式。")
        elif focus_sessions > 0 and completed_total == 0:
            parts.append("你已经有投入，但完成闭环还偏少，接下来更值得盯完成动作。")
        elif completed_total > 0 and focus_sessions == 0:
            parts.append("你有完成动作，但专注记录偏少，说明执行在发生，只是过程数据还不够。")
        else:
            parts.append("你已经有可观察的执行信号，接下来可以继续看哪些任务最常被推迟、哪些时段最容易推进。")
        reply = " ".join(parts)
    else:
        parts = [
            f"You currently have {active_count} active tasks.",
            f"Today you logged {focus_sessions} focus session(s) for {focus_minutes} minute(s).",
            f"You have completed {completed_total} task(s) in total.",
        ]
        if mood:
            parts.append(f"Your latest mood log is {mood.mood_level}/5.")
        if focus_sessions == 0 and completed_total == 0:
            parts.append("This still looks like a cold start, so finishing one small task or running one focus session would give me a much better signal.")
        elif focus_sessions > 0 and completed_total == 0:
            parts.append("You are putting in focus time, but completion is not closing the loop yet.")
        elif completed_total > 0 and focus_sessions == 0:
            parts.append("You are finishing tasks, but process data is still thin because focus sessions are missing.")
        else:
            parts.append("You already have enough execution signal to notice patterns, especially around deferrals and time-of-day consistency.")
        reply = " ".join(parts)

    return {
        "reply": reply,
        "requires_clarification": False,
        "clarification_question": "",
        "actions": [],
    }


def _looks_like_question(message: str) -> bool:
    normalized = (message or "").strip()
    lower = normalized.lower()
    if not normalized:
        return False
    if "?" in normalized or "？" in normalized:
        return True
    zh_starts = ("什么", "怎么", "为什么", "几点", "哪天", "哪天过", "哪里", "在哪", "是谁", "能不能", "可以吗", "是否", "干嘛")
    zh_contains = ("是什么", "什么时候", "在哪", "哪里", "怎么", "为什么", "几号", "哪天", "能不能", "可以不可以", "可以吗", "干嘛", "做什么", "有什么安排", "有啥安排", "有安排吗", "有哪些计划", "有什么计划", "计划是什么", "计划是哪些")
    en_starts = ("what", "when", "where", "why", "how", "who", "can you", "could you", "would you", "do i", "is it", "are you")
    return normalized.startswith(zh_starts) or any(token in normalized for token in zh_contains) or lower.startswith(en_starts)


def _has_explicit_command_intent(message: str) -> bool:
    normalized = (message or "").strip()
    lower = normalized.lower()
    zh_tokens = [
        "帮我", "请帮我", "麻烦你", "删掉", "删除", "去掉", "移除", "完成", "做完", "标记完成",
        "延后", "推迟", "标成", "改成", "加一个", "添加", "新增", "提醒我", "记一下", "生成计划",
        "刷新计划", "重新规划", "重排", "我要", "我想", "我得", "我需要",
    ]
    en_starts = (
        "add ", "add task", "delete ", "remove ", "drop ", "complete ", "finish ", "mark ",
        "defer ", "postpone ", "replan", "rebuild today", "regenerate plan", "refresh plan",
        "i need to", "i have to", "i should", "i want to",
    )
    return any(token in normalized for token in zh_tokens) or lower.startswith(en_starts)


def _mentions_birthday(message: str) -> bool:
    normalized = (message or "").strip().lower()
    return "生日" in normalized or "过生日" in normalized or "birthday" in normalized


def _mentions_other_person(message: str) -> bool:
    normalized = (message or "").strip().lower()
    zh_tokens = ("女朋友", "男朋友", "老婆", "老公", "对象", "朋友", "妈妈", "爸爸", "父母", "姐姐", "哥哥", "弟弟", "妹妹")
    en_tokens = ("girlfriend", "boyfriend", "wife", "husband", "partner", "friend", "mom", "mother", "dad", "father", "sister", "brother")
    return any(token in normalized for token in zh_tokens + en_tokens)


def _is_account_birthday_question(message: str) -> bool:
    if not _mentions_birthday(message) or not _looks_like_question(message):
        return False
    return not _mentions_other_person(message)


def _looks_like_scheduled_birthday_statement(message: str) -> bool:
    normalized = (message or "").strip()
    if not _mentions_birthday(message) or _looks_like_question(message):
        return False
    if _mentions_other_person(message):
        return True
    if _extract_due_date_hint(normalized):
        return True
    return bool(re.search(r"(下下|下|这|本)?(?:周|星期)([一二三四五六日天12345670])", normalized))


def _looks_like_smalltalk(message: str) -> bool:
    normalized = (message or "").strip().lower()
    if not normalized:
        return False
    zh = ("你好", "嗨", "哈喽", "谢谢", "多谢", "早上好", "晚上好")
    en = ("hi", "hello", "hey", "thanks", "thank you", "good morning", "good evening")
    return normalized.startswith(zh) or normalized.startswith(en)


def _looks_like_conversational_turn(message: str) -> bool:
    return (
        (_looks_like_question(message) and not _has_explicit_command_intent(message))
        or (_is_account_birthday_question(message) and not _has_explicit_command_intent(message))
        or _looks_like_smalltalk(message)
    )


def _safe_next_birthday(birthday: str) -> date | None:
    if not birthday:
        return None
    try:
        parsed = date.fromisoformat(birthday)
    except ValueError:
        return None
    today = local_today()
    target_year = today.year
    while True:
        try:
            candidate = date(target_year, parsed.month, parsed.day)
        except ValueError:
            candidate = date(target_year, 2, 28)
        if candidate >= today:
            return candidate
        target_year += 1


def _birthday_reply(ctx: Dict[str, Any], lang: str) -> Dict[str, Any]:
    birthday = (ctx.get("birthday") or "").strip()
    if not birthday:
        return {
            "reply": (
                "你现在还没有在账户里保存生日。去登录/设置里补上之后，我就能直接告诉你具体日期。"
                if lang == "zh"
                else "You don't have a birthday saved on your account yet. Add it in login/settings and I can answer it directly."
            ),
            "requires_clarification": False,
            "clarification_question": "",
            "actions": [],
        }

    next_birthday = _safe_next_birthday(birthday)
    month_day = birthday[5:].replace("-", "/")
    if lang == "zh":
        if next_birthday:
            reply = f"你保存的生日是 {birthday}，也就是 {int(month_day.split('/')[0])} 月 {int(month_day.split('/')[1])} 日。按当前日期算，下一次生日是 {next_birthday.isoformat()}。"
        else:
            reply = f"你保存的生日是 {birthday}。"
    else:
        reply = (
            f"Your saved birthday is {birthday}. Your next birthday is on {next_birthday.isoformat()}."
            if next_birthday
            else f"Your saved birthday is {birthday}."
        )
    return {
        "reply": reply,
        "requires_clarification": False,
        "clarification_question": "",
        "actions": [],
    }


def _looks_like_junk_task_title(title: str) -> bool:
    normalized = (title or "").strip().lower()
    if not normalized:
        return False
    if normalized.startswith("clarification:") or normalized.startswith("additional clarification:"):
        return True
    junk_fragments = (
        "有哪些任务",
        "有什么任务",
        "都需要干嘛",
        "有啥安排",
        "有安排吗",
        "是什么日期",
        "是什么时候",
        "what tasks",
        "what do i have",
        "what date is",
        "what day is",
    )
    if any(fragment in normalized for fragment in junk_fragments):
        return True
    return ("?" in normalized or "？" in normalized) and len(normalized) > 6


def _visible_tasks(tasks: List[Task]) -> List[Task]:
    return [task for task in list(tasks or []) if not _looks_like_junk_task_title(task.title)]


def _extract_task_date_question_query(message: str) -> str:
    normalized = (message or "").strip()
    lower = normalized.lower()
    if not normalized or not _looks_like_question(message):
        return ""

    zh_patterns = [
        r"^(.+?)的?日期是什么时候[？?]?$",
        r"^(.+?)是什么日期[？?]?$",
        r"^(.+?)是什么时候[？?]?$",
        r"^(.+?)在哪一天[？?]?$",
        r"^(.+?)是哪一天[？?]?$",
        r"^(.+?)是哪天[？?]?$",
        r"^(.+?)几号[？?]?$",
    ]
    en_patterns = [
        r"^when is (?:my task )?(.+?)[?]?$",
        r"^what date is (?:my task )?(.+?)[?]?$",
        r"^what day is (?:my task )?(.+?)[?]?$",
        r"^when do i have (.+?)[?]?$",
        r"^when is (.+?) scheduled[?]?$",
    ]

    extracted = ""
    for pattern in zh_patterns:
        match = re.match(pattern, normalized, flags=re.IGNORECASE)
        if match:
            extracted = match.group(1)
            break
    if not extracted:
        for pattern in en_patterns:
            match = re.match(pattern, lower, flags=re.IGNORECASE)
            if match:
                extracted = match.group(1)
                break

    cleaned = (extracted or "").strip()
    cleaned = re.sub(r"^(我的|我那个|那个|这个|任务[:：]?\s*|task[:：]?\s*)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(的任务|这个任务|那个任务)$", "", cleaned)
    return _normalize_task_query_text(cleaned)


def _weekday_label(weekday: int | None, lang: str) -> str:
    if weekday is None:
        return ""
    zh = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    if not 0 <= int(weekday) <= 6:
        return ""
    return zh[int(weekday)] if lang == "zh" else en[int(weekday)]


def _weekday_from_token(token: str) -> int | None:
    mapping = {
        "一": 0,
        "1": 0,
        "二": 1,
        "2": 1,
        "三": 2,
        "3": 2,
        "四": 3,
        "4": 3,
        "五": 4,
        "5": 4,
        "六": 5,
        "6": 5,
        "日": 6,
        "天": 6,
        "7": 6,
        "0": 6,
    }
    return mapping.get((token or "").strip())


def _relative_weekday_iso(prefix: str | None, weekday: int) -> str:
    normalized_prefix = (prefix or "").strip()
    if normalized_prefix in {"", "这", "本"}:
        return upcoming_weekday_iso(weekday)
    if normalized_prefix == "下":
        return next_weekday_iso(weekday)

    start_of_this_week = local_today() - timedelta(days=local_today().weekday())
    weeks_ahead = 2 if normalized_prefix == "下下" else 1
    return (start_of_this_week + timedelta(days=weeks_ahead * 7 + weekday)).isoformat()


def _task_matches_date(task: Task, date_key: str, weekday: int) -> bool:
    normalized_due_date = normalize_date_string(task.due_date)
    if task.task_kind == "daily":
        return not normalized_due_date or normalized_due_date <= date_key
    if task.task_kind == "weekly":
        if task.recurrence_weekday is None or int(task.recurrence_weekday) != weekday:
            return False
        return not normalized_due_date or normalized_due_date <= date_key
    return normalized_due_date == date_key


def _agenda_reply_for_date(ctx: Dict[str, Any], date_key: str, weekday: int, label: str, lang: str) -> Dict[str, Any]:
    tasks = [
        task
        for task in _visible_tasks(ctx.get("active_tasks", []) or [])
        if _task_matches_date(task, date_key, weekday)
    ]
    if not tasks:
        reply = (
            f"{label} 目前还没有挂上的安排。"
            if lang == "zh"
            else f"There is nothing scheduled for {label} yet."
        )
    else:
        titles = "、".join(task.title for task in tasks[:6]) if lang == "zh" else ", ".join(task.title for task in tasks[:6])
        reply = (
            f"{label} 目前有这些安排：{titles}。"
            if lang == "zh"
            else f"Here is what you have scheduled for {label}: {titles}."
        )
    return {
        "reply": reply,
        "requires_clarification": False,
        "clarification_question": "",
        "actions": [],
    }


def _agenda_reply_for_iso_date(ctx: Dict[str, Any], date_key: str, label: str, lang: str) -> Dict[str, Any] | None:
    try:
        weekday = date.fromisoformat(date_key).weekday()
    except ValueError:
        return None
    return _agenda_reply_for_date(ctx, date_key, weekday, label, lang)


def _history_before_current_user_message(history: Dict[str, Any], current_message: str) -> List[Dict[str, Any]]:
    messages = list((history or {}).get("messages", []) or [])
    if (
        messages
        and messages[-1].get("role") == "user"
        and (messages[-1].get("content") or "").strip() == (current_message or "").strip()
    ):
        return messages[:-1]
    return messages


def _recent_history_items(history: Dict[str, Any], current_message: str, roles: tuple[str, ...] | None = None) -> List[Dict[str, Any]]:
    items = _history_before_current_user_message(history, current_message)
    if roles:
        items = [item for item in items if item.get("role") in roles]
    return list(reversed(items[-12:]))


def _looks_like_agenda_query(message: str) -> bool:
    normalized = _strip_conversation_fillers((message or "").strip())
    if not normalized or _has_explicit_command_intent(normalized):
        return False
    patterns = [
        r"^我?(?:每周|每星期|每礼拜|周|星期|礼拜)([一二三四五六日天12345670])(?:都)?(?:需要)?(?:的计划(?:是哪些|是什么)?|计划(?:是哪些|是什么|有哪些)?|要做什么|做什么|干嘛|有哪些任务|有什么任务|有哪些安排|有什么安排|有啥安排|有安排吗)[？?]?$",
        r"^我?(?:(这|本|下|下下)周|(?:这|本|下|下下)星期)([一二三四五六日天12345670])(?:都)?(?:需要)?(?:的计划(?:是哪些|是什么)?|计划(?:是哪些|是什么|有哪些)?|要做什么|做什么|干嘛|有哪些任务|有什么任务|有哪些安排|有什么安排|有啥安排|有安排吗)[？?]?$",
        r"^(?:(这|本|下|下下)周|(?:这|本|下|下下)星期)([一二三四五六日天12345670])我?(?:的计划(?:是哪些|是什么)?|计划(?:是哪些|是什么|有哪些)?|有哪些任务|有什么任务|有哪些安排|有什么安排|有啥安排|有安排吗)[？?]?$",
        r"^那天(?:我)?(?:有哪些任务|有什么任务|有哪些安排|有什么安排|有啥安排|有安排吗|呢)[？?]?$",
        r"^那?(?:(这|本|下|下下)周|(?:这|本|下|下下)星期)([一二三四五六日天12345670])呢[？?]?$",
    ]
    return any(re.match(pattern, normalized) for pattern in patterns)


def _last_due_date_from_history(history: Dict[str, Any], current_message: str) -> str | None:
    for item in _recent_history_items(history, current_message, roles=("user",)):
        content = (item.get("content") or "").strip()
        due_date = _extract_due_date_hint(content) or _extract_plain_weekday_due_date(content)
        if due_date:
            return due_date
    return None


def _extract_task_title_from_assistant_summary(content: str) -> str:
    for line in (content or "").splitlines():
        match = re.match(
            r"^(?:已添加任务|已更新任务|已推迟任务|已完成任务|已删除任务|Added task|Updated task|Deferred task|Completed task|Deleted task)[:：]\s*(.+?)\s*$",
            line.strip(),
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
    return ""


def _last_task_reference_from_history(history: Dict[str, Any], current_message: str) -> str:
    for item in _recent_history_items(history, current_message):
        content = (item.get("content") or "").strip()
        if not content:
            continue
        if item.get("role") == "assistant":
            title = _extract_task_title_from_assistant_summary(content)
            if title:
                return title
            continue
        query = _extract_due_date_update_query(content)
        if query:
            return query
        query = _extract_task_date_question_query(content)
        if query:
            return query
        if _looks_like_scheduled_birthday_statement(content):
            title = _strip_due_hint(_canonical_task_text(content))
            if title:
                return title
        if not _looks_like_question(content) and (_has_explicit_command_intent(content) or _looks_like_structured_task_statement(content)):
            title = _strip_due_hint(_canonical_task_text(content))
            if title:
                return title
    return ""


def _agenda_focus_for_message(ctx: Dict[str, Any], message: str, history: Dict[str, Any], lang: str) -> Dict[str, Any] | None:
    normalized = _strip_conversation_fillers((message or "").strip())
    if not normalized or _has_explicit_command_intent(normalized):
        return None

    def build_focus(date_key: str, weekday: int, label: str) -> Dict[str, Any]:
        tasks = [
            task
            for task in _visible_tasks(ctx.get("active_tasks", []) or [])
            if _task_matches_date(task, date_key, weekday)
        ]
        return {"date_key": date_key, "weekday": weekday, "label": label, "tasks": tasks}

    weekly_match = re.match(
        r"^我?(?:每周|每星期|每礼拜|周|星期|礼拜)([一二三四五六日天12345670])(?:都)?(?:需要)?"
        r"(?:的计划(?:是哪些|是什么)?|计划(?:是哪些|是什么|有哪些)?|要做什么|做什么|干嘛|有哪些任务|有什么任务|有哪些安排|有什么安排|有啥安排|有安排吗)[？?]?$",
        normalized,
    )
    if weekly_match:
        weekday = _weekday_from_token(weekly_match.group(1))
        if weekday is not None:
            label = f"每{_weekday_label(weekday, lang)}" if lang == "zh" else f"every {_weekday_label(weekday, lang)}"
            return build_focus(upcoming_weekday_iso(weekday), weekday, label)

    dated_match = re.match(
        r"^我?(?:(这|本|下|下下)周|(?:这|本|下|下下)星期)([一二三四五六日天12345670])(?:都)?(?:需要)?"
        r"(?:的计划(?:是哪些|是什么)?|计划(?:是哪些|是什么|有哪些)?|要做什么|做什么|干嘛|有哪些任务|有什么任务|有哪些安排|有什么安排|有啥安排|有安排吗)[？?]?$",
        normalized,
    )
    if dated_match:
        prefix = dated_match.group(1)
        weekday = _weekday_from_token(dated_match.group(2))
        if weekday is not None:
            date_key = _relative_weekday_iso(prefix, weekday)
            return build_focus(date_key, weekday, f"{prefix}{_weekday_label(weekday, lang)}" if lang == "zh" else f"{prefix} {_weekday_label(weekday, lang)}")

    dated_subject_match = re.match(
        r"^(?:(这|本|下|下下)周|(?:这|本|下|下下)星期)([一二三四五六日天12345670])我?"
        r"(?:的计划(?:是哪些|是什么)?|计划(?:是哪些|是什么|有哪些)?|有哪些任务|有什么任务|有哪些安排|有什么安排|有啥安排|有安排吗)[？?]?$",
        normalized,
    )
    if dated_subject_match:
        prefix = dated_subject_match.group(1)
        weekday = _weekday_from_token(dated_subject_match.group(2))
        if weekday is not None:
            date_key = _relative_weekday_iso(prefix, weekday)
            return build_focus(date_key, weekday, f"{prefix}{_weekday_label(weekday, lang)}" if lang == "zh" else f"{prefix} {_weekday_label(weekday, lang)}")

    previous_user_messages = [
        (item.get("content") or "").strip()
        for item in _recent_history_items(history, message, roles=("user",))
    ]
    previous_agenda_context = any(_looks_like_agenda_query(item) for item in previous_user_messages)

    if re.match(r"^那天(?:我)?(?:有哪些任务|有什么任务|有哪些安排|有什么安排|有啥安排|有安排吗|呢)[？?]?$", normalized):
        date_key = _last_due_date_from_history(history, message)
        if date_key:
            try:
                weekday = date.fromisoformat(date_key).weekday()
            except ValueError:
                return None
            return build_focus(date_key, weekday, f"那天（{date_key}）" if lang == "zh" else f"that day ({date_key})")

    weekday_followup = re.match(
        r"^那?(?:(这|本|下|下下)周|(?:这|本|下|下下)星期)([一二三四五六日天12345670])呢[？?]?$",
        normalized,
    )
    if weekday_followup and previous_agenda_context:
        prefix = weekday_followup.group(1)
        weekday = _weekday_from_token(weekday_followup.group(2))
        if weekday is not None:
            return build_focus(_relative_weekday_iso(prefix, weekday), weekday, f"{prefix}{_weekday_label(weekday, lang)}" if lang == "zh" else f"{prefix} {_weekday_label(weekday, lang)}")

    weekly_followup = re.match(r"^那?(?:每周|每星期|每礼拜)([一二三四五六日天12345670])呢[？?]?$", normalized)
    if weekly_followup and previous_agenda_context:
        weekday = _weekday_from_token(weekly_followup.group(1))
        if weekday is not None:
            return build_focus(upcoming_weekday_iso(weekday), weekday, f"每{_weekday_label(weekday, lang)}" if lang == "zh" else f"every {_weekday_label(weekday, lang)}")

    generic_followup = re.match(r"^那?(.+?)呢[？?]?$", normalized)
    if generic_followup and previous_agenda_context:
        subject = generic_followup.group(1).strip()
        weekday_only = re.match(r"^(?:周|星期)([一二三四五六日天12345670])$", subject)
        if weekday_only:
            weekday = _weekday_from_token(weekday_only.group(1))
            if weekday is not None:
                return build_focus(upcoming_weekday_iso(weekday), weekday, _weekday_label(weekday, lang) if lang == "zh" else subject)
        date_key = _extract_due_date_hint(subject) or _extract_plain_weekday_due_date(subject)
        if date_key:
            try:
                weekday = date.fromisoformat(date_key).weekday()
            except ValueError:
                return None
            return build_focus(date_key, weekday, subject)

    return None


def _contextual_agenda_reply(ctx: Dict[str, Any], message: str, history: Dict[str, Any], lang: str) -> Dict[str, Any] | None:
    normalized = _strip_conversation_fillers((message or "").strip())
    if not normalized or _has_explicit_command_intent(normalized):
        return None
    previous_user_messages = [
        (item.get("content") or "").strip()
        for item in _recent_history_items(history, message, roles=("user",))
    ]
    previous_agenda_context = any(_looks_like_agenda_query(item) for item in previous_user_messages)

    if re.match(r"^那天(?:我)?(?:有哪些任务|有什么任务|有哪些安排|有什么安排|有啥安排|有安排吗|呢)[？?]?$", normalized):
        date_key = _last_due_date_from_history(history, message)
        if not date_key:
            return None
        label = f"那天（{date_key}）" if lang == "zh" else f"that day ({date_key})"
        return _agenda_reply_for_iso_date(ctx, date_key, label, lang)

    weekday_followup = re.match(
        r"^那?(?:(这|本|下|下下)周|(?:这|本|下|下下)星期)([一二三四五六日天12345670])呢[？?]?$",
        normalized,
    )
    if weekday_followup:
        if not previous_agenda_context:
            return None
        prefix = weekday_followup.group(1)
        weekday = _weekday_from_token(weekday_followup.group(2))
        if weekday is None:
            return None
        date_key = _relative_weekday_iso(prefix, weekday)
        weekday_label = _weekday_label(weekday, lang)
        label = f"{prefix}{weekday_label}" if lang == "zh" else f"{prefix} {weekday_label}"
        return _agenda_reply_for_date(ctx, date_key, weekday, label, lang)

    weekly_followup = re.match(r"^那?(?:每周|每星期|每礼拜)([一二三四五六日天12345670])呢[？?]?$", normalized)
    if weekly_followup and previous_agenda_context:
        weekday = _weekday_from_token(weekly_followup.group(1))
        if weekday is None:
            return None
        label = f"每{_weekday_label(weekday, lang)}" if lang == "zh" else f"every {_weekday_label(weekday, lang)}"
        return _agenda_reply_for_date(ctx, upcoming_weekday_iso(weekday), weekday, label, lang)

    generic_followup = re.match(r"^那?(.+?)呢[？?]?$", normalized)
    if generic_followup and previous_agenda_context:
        subject = generic_followup.group(1).strip()
        if re.match(r"^(?:周|星期)([一二三四五六日天12345670])$", subject):
            weekday = _weekday_from_token(re.match(r"^(?:周|星期)([一二三四五六日天12345670])$", subject).group(1))
            if weekday is None:
                return None
            label = _weekday_label(weekday, lang) if lang == "zh" else subject
            return _agenda_reply_for_date(ctx, upcoming_weekday_iso(weekday), weekday, label, lang)
        date_key = _extract_due_date_hint(subject) or _extract_plain_weekday_due_date(subject)
        if date_key:
            label = subject if lang == "zh" else subject
            return _agenda_reply_for_iso_date(ctx, date_key, label, lang)

    return None


def _task_agenda_reply(ctx: Dict[str, Any], message: str, lang: str) -> Dict[str, Any] | None:
    normalized = (message or "").strip()
    if not normalized or _has_explicit_command_intent(message):
        return None

    weekly_match = re.match(
        r"^我?(?:每周|每星期|每礼拜|周|星期|礼拜)([一二三四五六日天12345670])(?:都)?(?:需要)?"
        r"(?:的计划(?:是哪些|是什么)?|计划(?:是哪些|是什么|有哪些)?|要做什么|做什么|干嘛|有哪些任务|有什么任务|有哪些安排|有什么安排|有啥安排|有安排吗)[？?]?$",
        normalized,
    )
    if weekly_match:
        weekday = _weekday_from_token(weekly_match.group(1))
        if weekday is None:
            return None
        label = _weekday_label(weekday, lang)
        label = f"每{label}" if lang == "zh" else f"every {label}"
        return _agenda_reply_for_date(ctx, upcoming_weekday_iso(weekday), weekday, label, lang)

    dated_match = re.match(
        r"^我?(?:(这|本|下|下下)周|(?:这|本|下|下下)星期)([一二三四五六日天12345670])(?:都)?(?:需要)?"
        r"(?:的计划(?:是哪些|是什么)?|计划(?:是哪些|是什么|有哪些)?|要做什么|做什么|干嘛|有哪些任务|有什么任务|有哪些安排|有什么安排|有啥安排|有安排吗)[？?]?$",
        normalized,
    )
    if dated_match:
        prefix = dated_match.group(1)
        weekday = _weekday_from_token(dated_match.group(2))
        if weekday is None:
            return None
        date_key = _relative_weekday_iso(prefix, weekday)
        prefix_label = {
            "zh": {"这": "这", "本": "本", "下": "下", "下下": "下下"},
            "en": {"这": "this", "本": "this", "下": "next", "下下": "the following"},
        }
        weekday_label = _weekday_label(weekday, lang)
        label = (
            f"{prefix_label['zh'].get(prefix, prefix)}{weekday_label}"
            if lang == "zh"
            else f"{prefix_label['en'].get(prefix, 'that')} {weekday_label}"
        )
        return _agenda_reply_for_date(ctx, date_key, weekday, label, lang)

    dated_subject_match = re.match(
        r"^(?:(这|本|下|下下)周|(?:这|本|下|下下)星期)([一二三四五六日天12345670])我?"
        r"(?:的计划(?:是哪些|是什么)?|计划(?:是哪些|是什么|有哪些)?|有哪些任务|有什么任务|有哪些安排|有什么安排|有啥安排|有安排吗)[？?]?$",
        normalized,
    )
    if dated_subject_match:
        prefix = dated_subject_match.group(1)
        weekday = _weekday_from_token(dated_subject_match.group(2))
        if weekday is None:
            return None
        date_key = _relative_weekday_iso(prefix, weekday)
        weekday_label = _weekday_label(weekday, lang)
        label = f"{prefix}{weekday_label}" if lang == "zh" else f"{prefix} {weekday_label}"
        return _agenda_reply_for_date(ctx, date_key, weekday, label, lang)

    return None


def _task_schedule_reply(ctx: Dict[str, Any], message: str, lang: str, query_override: str = "") -> Dict[str, Any] | None:
    query = query_override or _extract_task_date_question_query(message)
    if not query:
        return None

    tasks = _visible_tasks(ctx.get("active_tasks", []) or [])
    resolution = _resolve_task_query(tasks, query)
    if resolution["status"] == "missing":
        return {
            "reply": (
                f"我在当前活跃任务里还没找到“{query}”。如果你指的是别的任务名，可以说得更完整一点。"
                if lang == "zh"
                else f"I couldn't find “{query}” in your active tasks. If you mean another task, give me a more complete title."
            ),
            "requires_clarification": False,
            "clarification_question": "",
            "actions": [],
        }
    if resolution["status"] == "ambiguous":
        labels = "；".join(
            f"{index + 1}. {item['title']}" if lang == "zh" else f"{index + 1}. {item['title']}"
            for index, item in enumerate(resolution["matches"])
        )
        return {
            "reply": (
                f"我找到了多个可能的任务：{labels}。你告诉我具体是哪一个，我就能继续回答日期。"
                if lang == "zh"
                else f"I found multiple matching tasks: {labels}. Tell me which one you mean and I can answer the date."
            ),
            "requires_clarification": False,
            "clarification_question": "",
            "actions": [],
        }

    task = resolution["task"]
    if task.due_date:
        reply = (
            f"任务“{task.title}”现在定在 {task.due_date}。"
            if lang == "zh"
            else f"Your task “{task.title}” is currently scheduled for {task.due_date}."
        )
    elif task.task_kind == "weekly" and task.recurrence_weekday is not None:
        weekday_label = _weekday_label(task.recurrence_weekday, lang)
        reply = (
            f"任务“{task.title}”是每{weekday_label}。"
            if lang == "zh"
            else f"Your task “{task.title}” repeats every {weekday_label}."
        )
    elif task.task_kind == "daily":
        reply = (
            f"任务“{task.title}”是每天都会出现的日常任务。"
            if lang == "zh"
            else f"Your task “{task.title}” is a daily recurring task."
        )
    else:
        reply = (
            f"任务“{task.title}”现在还没有设置具体日期。"
            if lang == "zh"
            else f"Your task “{task.title}” does not have a specific date set yet."
        )

    return {
        "reply": reply,
        "requires_clarification": False,
        "clarification_question": "",
        "actions": [],
    }


def _contextual_task_schedule_reply(ctx: Dict[str, Any], message: str, history: Dict[str, Any], lang: str) -> Dict[str, Any] | None:
    normalized = _strip_conversation_fillers((message or "").strip())
    if not normalized or _has_explicit_command_intent(normalized):
        return None
    if not re.match(
        r"^(?:那)?(?:这个|那个)?任务(?:呢)?(?:的)?(?:日期是什么时候|是什么日期|是什么时候|在哪一天|是哪一天|是哪天|几号)[？?]?$",
        normalized,
    ):
        return None
    query = _last_task_reference_from_history(history, message)
    if not query:
        return None
    return _task_schedule_reply(ctx, message, lang, query_override=query)


def _general_chat_reply(message: str, ctx: Dict[str, Any], lang: str) -> Dict[str, Any] | None:
    normalized = (message or "").strip()
    lower = normalized.lower()

    if _is_account_birthday_question(message):
        if _looks_like_question(message):
            return _birthday_reply(ctx, lang)
    if _looks_like_scheduled_birthday_statement(message):
        return None
    if _mentions_birthday(message) and not _mentions_other_person(message):
        return {
            "reply": (
                "那先提前祝你生日快乐。你如果想，我也可以顺手帮你加一个生日提醒任务，但我现在先不自动改任务。"
                if lang == "zh"
                else "Happy early birthday. If you want, I can add a birthday reminder task, but I won't change anything automatically."
            ),
            "requires_clarification": False,
            "clarification_question": "",
            "actions": [],
        }

    if any(token in lower for token in ["what can you do", "help me with", "can you do"]) or any(
        token in normalized for token in ["你能做什么", "你可以做什么", "你会什么", "能帮我什么"]
    ):
        return {
            "reply": (
                "我现在既可以执行站内动作，也可以普通问答。你可以问我任务、计划、专注记录、生日日期这些站内信息；如果你明确让我改任务，我再动手。"
                if lang == "zh"
                else "I can now both take in-app actions and do normal Q&A. You can ask about tasks, plans, focus logs, or account info, and I only change things when you explicitly ask me to."
            ),
            "requires_clarification": False,
            "clarification_question": "",
            "actions": [],
        }

    if any(token in lower for token in ["what day is it", "today's date", "what date is it"]) or any(
        token in normalized for token in ["今天几号", "今天是什么日期", "今天几月几号", "今天是哪天"]
    ):
        return {
            "reply": (
                f"今天是 {ctx.get('today')}。"
                if lang == "zh"
                else f"Today is {ctx.get('today')}."
            ),
            "requires_clarification": False,
            "clarification_question": "",
            "actions": [],
        }

    if _looks_like_smalltalk(message):
        return {
            "reply": (
                "在。我现在也可以普通聊天和答疑，不只会改任务。"
                if lang == "zh"
                else "I'm here. I can do normal chat and Q&A too, not just task changes."
            ),
            "requires_clarification": False,
            "clarification_question": "",
            "actions": [],
        }

    return None


def _looks_like_fresh_request(message: str) -> bool:
    normalized = (message or "").strip().lower()
    if not normalized:
        return False
    prefixes = [
        "add ",
        "add task",
        "task:",
        "delete ",
        "remove ",
        "drop ",
        "complete ",
        "finish ",
        "mark ",
        "mark done",
        "defer ",
        "postpone ",
        "replan",
        "rebuild today",
        "regenerate plan",
        "refresh plan",
        "analyze",
        "analyse",
        "what tasks",
        "what do i have",
        "current tasks",
        "show my tasks",
        "list my tasks",
    ]
    zh_prefixes = [
        "帮我",
        "给我",
        "加",
        "添加",
        "新增",
        "删",
        "删除",
        "去掉",
        "移除",
        "完成",
        "做完",
        "标记完成",
        "延后",
        "推迟",
        "重排",
        "重新规划",
        "刷新计划",
        "重建今天",
        "分析",
        "看看",
    ]
    return (
        normalized.startswith(tuple(prefixes))
        or normalized.startswith(tuple(zh_prefixes))
        or _looks_like_structured_task_statement(message)
        or _looks_like_conversational_turn(message)
        or _looks_like_scheduled_birthday_statement(message)
    )


def _sanitize_assistant_text(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return ""
    cleaned = cleaned.replace("Additional clarification:", "").replace("Clarification:", "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _strip_conversation_fillers(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    while True:
        updated = re.sub(r"^(?:那(?!天|周|星期|个|下|这|本)|然后|哦|噢|啊|嗯|呃|额)[，,\s]*", "", cleaned)
        if updated == cleaned:
            break
        cleaned = updated.strip()
    return cleaned


def _normalize_task_title_text(text: str) -> str:
    cleaned = _strip_conversation_fillers(text)
    if not cleaned:
        return ""

    clarification_patterns = [
        r"^.*\n(?:Additional clarification|Clarification)[:：]\s*",
        r"^(?:Additional clarification|Clarification)[:：]\s*",
        r"^补充说明[:：]\s*",
        r"^补充[:：]\s*",
    ]
    for pattern in clarification_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL)

    patterns = [
        r"^(帮我|给我|请|麻烦你)?\s*(加上一个|加入一个|添加一个|新增一个|加一个|加一项|加一条|加上|加入|添加|新增|加个|记录一下)\s*",
        r"^(帮我|给我|请|麻烦你)?\s*(add|create)\s+(a\s+)?(task:?\s*)?",
        r"^(任务[:：]\s*)",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Strip recurring/date shells from natural Chinese task phrases so the title
    # only keeps the actual thing to do.
    recurring_shell_patterns = [
        r"^(?:我)?(?:(?:这|本|下|下下)?(?:每周|每星期|每礼拜|周|星期|礼拜))[一二三四五六日天12345670]\s*(?:有个|有|要去|要做|要|得去|得做|得|会有|会去|会做)?\s*",
        r"^(?:我)?(?:(?:这|本|下|下下)?(?:每周|每星期|每礼拜|周|星期|礼拜))[一二三四五六日天12345670]\s*",
    ]
    for pattern in recurring_shell_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"(?:这|本|下|下下)(?:周|星期)[一二三四五六日天12345670]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(这个|一个|一项|一条|一个要|一个去)\s*", "", cleaned)
    cleaned = re.sub(r"(这个|一个|一项|一条)\s*$", "", cleaned)
    cleaned = re.sub(r"(这个)?任务$", "", cleaned)
    cleaned = re.sub(r"的$", "", cleaned)
    cleaned = re.sub(r"[。．.!！]+$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ：:，,.")
    return cleaned


def _normalize_task_query_text(text: str) -> str:
    cleaned = _strip_conversation_fillers(text)
    if not cleaned:
        return ""
    cleaned = re.sub(r"^(帮我|给我|请|麻烦你)?\s*(把|吧)?", "", cleaned)
    cleaned = re.sub(
        r"^(delete|remove|drop|complete|finish|defer|postpone|mark done|mark|mark as)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"(删掉|删除|去掉|移除|完成|做完|标记完成|延后|推迟|稍后再做|标成临时|改成临时|临时任务|标成每日|改成每日|日常任务|每天任务)$", "", cleaned)
    cleaned = re.sub(r"\s+as\s+(daily|temporary)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(这个|那个)?任务$", "", cleaned)
    cleaned = re.sub(r"的$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ：:，,.")
    return cleaned


def _canonical_task_text(text: str) -> str:
    cleaned = _normalize_task_title_text(text)
    if not cleaned:
        cleaned = _normalize_task_query_text(text)
    cleaned = re.sub(r"^(我要|我想|我得|我需要|今天要|等会要)\s*", "", cleaned)
    cleaned = re.sub(r"^(都要|都得|都需要|都会)\s*", "", cleaned)
    cleaned = re.sub(r"^(?:i\s+)?(?:need to|have to|should|want to)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def _compact_task_text(text: str) -> str:
    return re.sub(r"\s+", "", _canonical_task_text(text))


def _extract_all_recurrence_weekdays(text: str) -> List[int]:
    combined = (text or "").strip().lower()
    if not combined:
        return []
    weekdays: List[int] = []
    for weekday, patterns in WEEKDAY_PATTERNS:
        if any(re.search(pattern, combined, flags=re.IGNORECASE) for pattern in patterns):
            weekdays.append(weekday)
    return sorted(set(weekdays))


SEMANTIC_REPLACEMENTS = [
    (r"(吃午饭|午饭|吃午餐|午餐|eatlunch|havelunch|lunch)", "lunch"),
    (r"(吃早饭|早餐|早饭|eatbreakfast|havebreakfast|breakfast)", "breakfast"),
    (r"(吃晚饭|晚饭|晚餐|eatdinner|havedinner|dinner|supper)", "dinner"),
    (r"(睡觉|sleeping|sleep)", "sleep"),
    (r"(跑步|running|run)", "run"),
    (r"(遛狗|walkdog|dogwalk)", "walkdog"),
    (r"(买咖啡|喝咖啡|buycoffee|getcoffee|coffee)", "coffee"),
    (r"(买菜|买 groceries|groceries|groceryshopping|grocery)", "groceries"),
]


def _semantic_task_key(text: str) -> str:
    compact = _compact_task_text(text)
    if not compact:
        return ""
    normalized = re.sub(r"(这个|那个)?任务$", "", compact)
    normalized = normalized.replace("的", "")
    for pattern, replacement in SEMANTIC_REPLACEMENTS:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return normalized


def _extract_due_date_hint(message: str) -> str | None:
    normalized = (message or "").strip().lower()
    if not normalized:
        return None
    explicit_match = re.search(r"(\d{4}[./]\d{1,2}[./]\d{1,2}|\d{1,2}[./-]\d{1,2})", message)
    if explicit_match:
        normalized_date = normalize_date_string(explicit_match.group(1))
        if normalized_date:
            return normalized_date
    weekday_map = {
        "monday": 0, "mon": 0,
        "tuesday": 1, "tue": 1,
        "wednesday": 2, "wed": 2,
        "thursday": 3, "thu": 3,
        "friday": 4, "fri": 4,
        "saturday": 5, "sat": 5,
        "sunday": 6, "sun": 6,
    }
    zh_weekday_map = {
        "周一": 0, "星期一": 0, "周1": 0, "星期1": 0,
        "周二": 1, "星期二": 1, "周2": 1, "星期2": 1,
        "周三": 2, "星期三": 2, "周3": 2, "星期3": 2,
        "周四": 3, "星期四": 3, "周4": 3, "星期4": 3,
        "周五": 4, "星期五": 4, "周5": 4, "星期5": 4,
        "周六": 5, "星期六": 5, "周6": 5, "星期6": 5,
        "周日": 6, "周天": 6, "星期日": 6, "星期天": 6, "周7": 6, "星期7": 6,
    }
    explicit_relative_zh = re.search(r"(下下|下|这|本)?(?:周|星期)([一二三四五六日天12345670])", message)
    if explicit_relative_zh:
        weekday = _weekday_from_token(explicit_relative_zh.group(2))
        if weekday is not None:
            return _relative_weekday_iso(explicit_relative_zh.group(1), weekday)
    for token, weekday in weekday_map.items():
        if re.search(rf"\bthis {re.escape(token)}\b", normalized):
            return upcoming_weekday_iso(weekday)
        if re.search(rf"\bnext {re.escape(token)}\b", normalized):
            return next_weekday_iso(weekday)
    for token, weekday in zh_weekday_map.items():
        if f"这{token}" in message or f"本{token}" in message or f"到这{token}" in message or f"到本{token}" in message:
            return upcoming_weekday_iso(weekday)
        if f"下{token}" in message or f"到下{token}" in message or f"下星期{token[-1]}" in message:
            return next_weekday_iso(weekday)
    if re.search(r"\bnext month\b", normalized) or "下个月" in message:
        return next_month_iso()
    if any(token in normalized for token in ["this weekend", "next weekend", "weekend"]) or any(
        token in message for token in ["这个周末", "这周末", "本周末", "下周末", "周末"]
    ):
        return upcoming_weekend_iso()
    if "下周" in message or "下星期" in message or re.search(r"\bnext week\b", normalized):
        return next_week_iso()
    if "大后天" in message or "three days later" in normalized:
        return local_date_offset_iso(3)
    if any(token in normalized for token in ["day after tomorrow", "after tomorrow"]) or any(token in message for token in ["后天"]):
        return local_date_offset_iso(2)
    if any(re.search(rf"\b{re.escape(token)}\b", normalized) for token in ["tomorrow morning", "tomorrow", "tmr"]) or any(token in message for token in ["明天", "明早"]):
        return local_date_offset_iso(1)
    if any(re.search(rf"\b{re.escape(token)}\b", normalized) for token in ["tonight", "this evening", "today"]) or any(token in message for token in ["今晚", "今夜", "今天"]):
        return local_date_offset_iso(0)
    return None


def _extract_plain_weekday_due_date(message: str) -> str | None:
    normalized = (message or "").strip().lower()
    if not normalized:
        return None
    if any(token in normalized for token in ["every ", "weekly", "each week"]) or any(
        token in message for token in ["每周", "每星期"]
    ):
        return None
    weekday_map = {
        "monday": 0, "mon": 0,
        "tuesday": 1, "tue": 1,
        "wednesday": 2, "wed": 2,
        "thursday": 3, "thu": 3,
        "friday": 4, "fri": 4,
        "saturday": 5, "sat": 5,
        "sunday": 6, "sun": 6,
    }
    zh_weekday_map = {
        "周一": 0, "星期一": 0,
        "周二": 1, "星期二": 1,
        "周三": 2, "星期三": 2,
        "周四": 3, "星期四": 3,
        "周五": 4, "星期五": 4,
        "周六": 5, "星期六": 5,
        "周日": 6, "周天": 6, "星期日": 6, "星期天": 6,
    }
    for token, weekday in zh_weekday_map.items():
        if token in message:
            return upcoming_weekday_iso(weekday)
    for token, weekday in weekday_map.items():
        if re.search(rf"\b{re.escape(token)}\b", normalized):
            return upcoming_weekday_iso(weekday)
    return None


def _extract_due_date_update_query(message: str) -> str:
    normalized = (message or "").strip()
    lower = normalized.lower()
    zh_match = re.match(
        r"^(?:帮我|给我|请|麻烦你)?\s*(?:把)?\s*(.+?)\s*(?:的ddl|的截止日期|的截止时间|的deadline|ddl|截止日期|截止时间|截止|deadline)?\s*(?:设置到|设到|改到|调到|安排到)\s*(.+)$",
        normalized,
        flags=re.IGNORECASE,
    )
    if zh_match:
        return _normalize_task_query_text(zh_match.group(1))

    en_match = re.match(
        r"^(?:help me\s+)?(?:set|move|schedule)\s+(.+?)\s+(?:deadline|due date|due)\s+(?:to|for)\s+(.+)$",
        lower,
        flags=re.IGNORECASE,
    )
    if en_match:
        return _normalize_task_query_text(en_match.group(1))

    return ""


def _strip_due_hint(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(
        r"^(\d{4}[./]\d{1,2}[./]\d{1,2}|\d{1,2}[./-]\d{1,2})\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^(明天|明早|后天|大后天|下个月|这个周末|这周末|本周末|下周末|周末|今晚|今夜|今天"
        r"|下周[一二三四五六日天]?|下星期[一二三四五六日天]?|这周[一二三四五六日天]?|本周[一二三四五六日天]?)\s*",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"^(tomorrow morning|tomorrow|tonight|this evening|today|next week|next month|this weekend|next weekend|weekend"
        r"|this\s+(monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat|sunday|sun)"
        r"|next\s+(monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat|sunday|sun)"
        r"|on\s+(monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat|sunday|sun))\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(\s+to\s+next\s+(monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat|sunday|sun)"
        r"|\s+to\s+this\s+(monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat|sunday|sun)"
        r"|\s+this\s+(monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat|sunday|sun)"
        r"|\s+next\s+(monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat|sunday|sun)"
        r"|\s+on\s+(monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat|sunday|sun)"
        r"|\s+(monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat|sunday|sun)"
        r"|\s+to\s+next\s+week|\s+next\s+week|\s+to\s+next\s+month|\s+next\s+month"
        r"|\s+to\s+this\s+weekend|\s+this\s+weekend|\s+to\s+next\s+weekend|\s+next\s+weekend|\s+weekend"
        r"|\s+three\s+days\s+later"
        r"|\s+to\s+the\s+day\s+after\s+tomorrow|\s+the\s+day\s+after\s+tomorrow|\s+after\s+tomorrow"
        r"|\s+to\s+tomorrow\s+morning|\s+tomorrow\s+morning|\s+to\s+tomorrow|\s+by\s+tomorrow"
        r"|\s+to\s+tonight|\s+by\s+tonight|\s+tonight|\s+to\s+this\s+evening|\s+this\s+evening"
        r"|\s+(\d{4}[./]\d{1,2}[./]\d{1,2}|\d{1,2}[./-]\d{1,2})"
        r"|到下个月|下个月|到这个周末|这个周末|到这周末|这周末|到本周末|本周末|到下周末|下周末|到周末|周末"
        r"|到大后天|大后天|到后天|后天|到明天|明天|明早|到今晚|今晚|今夜|到下周[一二三四五六日天]?|下周[一二三四五六日天]?|到下星期[一二三四五六日天]?|下星期[一二三四五六日天]?|tomorrow)$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", cleaned).strip(" ：:，,.")


def _build_action_reply(reply: str, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "reply": reply,
        "requires_clarification": False,
        "clarification_question": "",
        "actions": actions,
    }


def _try_compound_action(message: str, lang: str) -> Dict[str, Any] | None:
    normalized = message.strip()
    lower = normalized.lower()

    zh_delete_add = re.match(r"^.*?(删掉|删除|去掉|移除)(.+?)(再加|然后加|再添加|再新增)(.+)$", normalized)
    if zh_delete_add:
        delete_part = _normalize_task_query_text(zh_delete_add.group(2))
        add_part = _normalize_task_title_text(zh_delete_add.group(4))
        if delete_part and add_part:
            return _build_action_reply("", [
                {"type": "delete_task", "task_query": delete_part},
                {"type": "add_task", "title": add_part, "description": "", "priority": 0, "due_date": None},
            ])

    en_delete_add = re.match(r"^(delete|remove|drop)\s+(.+?)\s+(and add|and create)\s+(.+)$", lower, flags=re.IGNORECASE)
    if en_delete_add:
        delete_part = _normalize_task_query_text(en_delete_add.group(2))
        add_part = _normalize_task_title_text(en_delete_add.group(4))
        if delete_part and add_part:
            return _build_action_reply("", [
                {"type": "delete_task", "task_query": delete_part},
                {"type": "add_task", "title": add_part, "description": "", "priority": 0, "due_date": None},
            ])

    zh_two_adds = re.match(
        r"^(我要|我想|我得|我需要)\s*(.+?)(?:，|,)?(?:然后|再|并且)\s*(?:明天)?(?:提醒我|记得|让我)\s*(.+?)(?:到?明天|明早)?$",
        normalized,
    )
    if zh_two_adds:
        first_title = _canonical_task_text(zh_two_adds.group(2))
        second_title = _canonical_task_text(zh_two_adds.group(3))
        if first_title and second_title:
            return _build_action_reply("", [
                {"type": "add_task", "title": first_title, "description": "", "priority": 0, "due_date": None},
                {"type": "add_task", "title": second_title, "description": "", "priority": 0, "due_date": local_date_offset_iso(1)},
            ])

    en_reminder = re.match(r"^(i need to|i have to|i should|i want to)\s+(.+?),?\s+and\s+remind me to\s+(.+?)\s+tomorrow$", lower, flags=re.IGNORECASE)
    if en_reminder:
        first_title = _canonical_task_text(en_reminder.group(2))
        second_title = _canonical_task_text(en_reminder.group(3))
        if first_title and second_title:
            return _build_action_reply("", [
                {"type": "add_task", "title": first_title, "description": "", "priority": 0, "due_date": None},
                {"type": "add_task", "title": second_title, "description": "", "priority": 0, "due_date": local_date_offset_iso(1)},
            ])

    return None


def _looks_like_structured_task_statement(message: str) -> bool:
    normalized = (message or "").strip()
    lower = normalized.lower()
    return any([
        bool(re.match(r"^(我要|我想|我得|我需要|今天要|等会要)\s*\S+", normalized)),
        bool(re.match(r"^(?:我)?(?:每天|每日|每天都|每日都)\s*(?:要|得|需要|会)?\s*\S+", normalized)),
        bool(re.match(r"^(i need to|i have to|i should|i want to)\s+\S+", lower)),
        bool(re.match(r"^(?:i )?(?:every day|daily)\s+\S+", lower)),
        bool(re.match(r"^(?:i\s+)?(.+?)\s+every day$", lower)),
        bool(re.match(r"^i\s+have\s+(?:a\s+)?plans?\s+(?:on\s+)?every\s+(.+?)\s+to\s+(.+)$", normalized, flags=re.IGNORECASE)),
        bool(re.match(r"^(我)?(?:(?:这|本|下|下下)周|(?:这|本|下|下下)星期)([一二三四五六日天12345670]).*(.+)$", normalized)),
        bool(re.match(r"^(我)?(?:每周|每星期|每礼拜|周|星期|礼拜)([一二三四五六日天12345670]).*(.+)$", normalized)),
        bool(re.match(r"^(帮我|给我|请|麻烦你)?\s*(加上|加入|添加|新增|加个|加一个|加一项|记录一下)", normalized)),
        bool(re.match(r"^(add|create)\s+((a|an)\s+)?", lower)),
    ])


def _should_prefer_llm_for_turn(message: str, llm_available: bool) -> bool:
    if not llm_available:
        return False
    return True


def _coerce_llm_assistant_reply(parsed: Dict[str, Any], message: str) -> Dict[str, Any]:
    normalized = (message or "").strip()
    if _looks_like_question(normalized) and not _has_explicit_command_intent(normalized):
        parsed["actions"] = []
    for action in parsed.get("actions", []):
        if action.get("type") == "add_task":
            action["title"] = _normalize_task_title_text(action.get("title", ""))
            derived_due_date = (
                normalize_date_string(action.get("due_date"))
                or infer_relative_due_date(action.get("title", ""), action.get("description") or "")
                or infer_relative_due_date(message, action.get("description") or "")
            )
            if derived_due_date:
                action["due_date"] = derived_due_date
                if action.get("task_kind") == "weekly":
                    action["task_kind"] = "temporary"
                    action["recurrence_weekday"] = None
            if not action.get("task_kind"):
                action["task_kind"] = infer_task_kind(
                    message,
                    action.get("description") or "",
                    action.get("due_date"),
                    None,
                )
            if action.get("task_kind") == "weekly" and action.get("recurrence_weekday") is None:
                action["recurrence_weekday"] = infer_recurrence_weekday(
                    message,
                    action.get("description") or "",
                )
        if action.get("task_query"):
            action["task_query"] = _normalize_task_query_text(action.get("task_query", ""))
    return parsed


def _try_llm_assistant_reply(
    llm: Any,
    message: str,
    lang: str,
    profile: Dict[str, Any],
    history: Dict[str, Any],
    ctx: Dict[str, Any],
) -> Dict[str, Any] | None:
    recent = history.get("messages", [])[-8:]
    conversation = "\n".join(f'{item["role"]}: {item["content"]}' for item in recent)
    profile_summary = profile.get("summary", "")
    active_tasks = ctx.get("active_tasks", [])
    plan_tasks = ctx.get("plan_tasks", [])
    mood = ctx.get("mood")
    agenda_focus = _agenda_focus_for_message(ctx, message, history, lang)
    agenda_focus_block = ""
    if agenda_focus:
        matching_titles = "\n".join(f"- {task.title}" for task in agenda_focus["tasks"]) or "- (none)"
        agenda_focus_block = f"""

Resolved agenda focus for this request:
- Scope: {agenda_focus["label"]} ({agenda_focus["date_key"]})
- Matching tasks only:
{matching_titles}
- Do not mention tasks outside this scope unless the user explicitly asked for all tasks.
"""
    prompt = f"""You are the user's private concierge inside a planning app.
You should be conversation-first, grounded in the real app data below, and only produce actions when the user is actually asking you to change something.

Current profile summary:
{profile_summary or "(none yet)"}

Current date:
{ctx.get("today")}

User account:
- Display name: {ctx.get("display_name") or "(unknown)"}
- Birthday: {ctx.get("birthday") or "(not set)"}

Today's planned tasks:
{_task_titles(plan_tasks)}

Active tasks:
{_task_titles(active_tasks)}

Current mood:
{f'level {mood.mood_level}/5, note: {mood.note}' if mood else '(not logged)'}

Focus today:
{ctx.get("focus_today_sessions", 0)} sessions / {ctx.get("focus_today_minutes", 0)} minutes

Completed tasks total:
{ctx.get("completed_total", 0)}

Recent conversation:
{conversation or '(none)'}

User message:
{message}
{agenda_focus_block}

Rules:
- Answer normal questions directly from the app context. Do not create, update, delete, complete, or defer tasks unless the user is clearly asking you to do that.
- For schedule questions like "我每周四有哪些任务", "我每周二的计划是哪些", "what is my plan for every Tuesday", or "那天我有什么安排", answer only for that date/weekday. Do NOT dump the full active task list unless the user explicitly asks for all tasks.
- Use the recent conversation to resolve references like "那天", "那周三", "那个任务", or "that day".
- If the user asks when an existing task happens, answer from the task/date context instead of modifying anything.
- If the user asks for all current tasks, then and only then list all active tasks.
- If the user naturally describes a real plan or appointment to remember, you may convert it into an add_task even if they did not use an imperative command.
- Treat short first-person routine statements in both Chinese and English as task creation when they clearly describe a habit or recurring plan. Examples: "我每天都要做饭", "我每天喝两升水", "I cook every day", "I need to work out every day".
- Treat direct action requests in both Chinese and English as concrete task operations even if the task name is phrased loosely. Examples: "帮我删除喝两升水的任务", "把喝水那个删了", "delete the water task", "remove my drink water task".
- Extract clean task titles only. Remove wrappers like "帮我加一个", "加上", "task", "任务", or date shells.
- Prefer concise, natural wording. Be helpful, grounded, and specific.
- If the request is ambiguous, ask one short clarification question.

Return valid JSON only:
{{
  "reply": "assistant response to show in chat",
  "requires_clarification": true/false,
  "clarification_question": "question if needed, otherwise empty",
  "actions": [
    {{
      "type": "add_task|delete_task|update_task|complete_task|defer_task|generate_plan|log_mood",
      "task_query": "task name if needed",
      "title": "new title if needed",
      "description": "optional",
      "task_kind": "daily|temporary|weekly|null",
      "recurrence_weekday": null,
      "priority": 0,
      "due_date": null,
      "mood_level": null,
      "note": ""
    }}
  ]
}}"""

    try:
        raw = llm._call_deepseek(
            "You are a precise product concierge. Return valid JSON only.",
            prompt,
            max_tokens=900,
        )
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return _coerce_llm_assistant_reply(parsed, message)
    except Exception:
        return None
    return None


def _call_assistant_llm(message: str, lang: str, profile: Dict[str, Any], history: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    lower = message.lower()
    normalized = message.strip()
    llm = get_llm_service(lang=lang)
    llm_available = bool(hasattr(llm, "_call_deepseek") and getattr(llm, "api_key", ""))
    llm_first_attempted = False
    llm_first_reply = None

    def action_reply(reply: str, action: Dict[str, Any]) -> Dict[str, Any]:
        return _build_action_reply(reply, [action])

    compound = _try_compound_action(normalized, lang)
    if compound:
        return compound

    if any(token in lower for token in ["least important", "least useful", "least valuable", "least worth"]) or any(
        token in normalized for token in ["最不重要", "最次要", "最没那么重要", "最没用", "最无用", "最没价值"]
    ):
        return {
            "reply": (
                "这一步我不替你判断哪个最没用。你直接告诉我要删哪一个，或者给我两个候选，我可以帮你执行。"
                if lang == "zh"
                else "I won't decide which task is least useful for you. Tell me which one to remove, or give me two candidates and I'll execute your choice."
            ),
            "requires_clarification": False,
            "clarification_question": "",
            "actions": [],
        }

    if _should_prefer_llm_for_turn(message, llm_available):
        llm_first_attempted = True
        llm_first_reply = _try_llm_assistant_reply(llm, message, lang, profile, history, ctx)
        if llm_first_reply and (
            llm_first_reply.get("reply")
            or llm_first_reply.get("actions")
            or llm_first_reply.get("requires_clarification")
        ):
            return llm_first_reply

    allow_natural_language_fast_paths = (
        (not llm_available)
        or (llm_first_attempted and not llm_first_reply)
    )

    contextual_agenda_reply = _contextual_agenda_reply(ctx, message, history, lang)
    if contextual_agenda_reply:
        return contextual_agenda_reply

    contextual_schedule_reply = _contextual_task_schedule_reply(ctx, message, history, lang)
    if contextual_schedule_reply and not _has_explicit_command_intent(message):
        return contextual_schedule_reply

    chat_reply = _general_chat_reply(message, ctx, lang)
    if chat_reply and not _has_explicit_command_intent(message):
        return chat_reply

    agenda_reply = _task_agenda_reply(ctx, message, lang)
    if agenda_reply:
        return agenda_reply

    if _looks_like_scheduled_birthday_statement(message):
        title = _strip_due_hint(_canonical_task_text(normalized))
        due_date = _extract_due_date_hint(normalized) or _extract_plain_weekday_due_date(normalized)
        if title:
            return action_reply(
                "",
                {"type": "add_task", "title": title, "description": "", "priority": 0, "due_date": due_date},
            )

    if any(token in normalized for token in ["有哪些任务", "现在有什么任务", "当前有什么任务", "我现在有哪些任务", "任务列表"]) or any(
        token in lower for token in ["what tasks", "what do i have", "current tasks", "show my tasks", "list my tasks"]
    ):
        return _list_tasks_reply(ctx, lang)

    if any(token in normalized for token in ["分析", "看看我最近", "分析一下我最近", "最近的专注", "完成情况"]) or any(
        token in lower for token in ["analyze", "analyse", "focus and completion", "completion pattern", "focus pattern"]
    ):
        return _analysis_reply(ctx, lang)

    task_schedule_reply = _task_schedule_reply(ctx, message, lang)
    if task_schedule_reply and not _has_explicit_command_intent(message):
        return task_schedule_reply

    # Keep only very structured fast paths. Natural-language requests should go
    # through DeepSeek so the concierge feels less mechanical.
    if any(token in lower for token in ["replan", "rebuild today", "regenerate plan", "refresh plan"]) or any(
        token in normalized for token in ["重排", "重新规划", "刷新计划", "重建今天"]
    ):
        return action_reply(
            "",
            {"type": "generate_plan"},
        )

    if normalized.lower().startswith(("complete task:", "finish task:", "mark done:", "complete ", "finish ")) or any(
        token in normalized for token in ["完成", "做完", "标记完成"]
    ):
        task_query = normalized
        for token in ["帮我", "把", "吧", "完成", "做完", "标记完成", "complete task:", "finish task:", "mark done:", "complete ", "finish "]:
            task_query = task_query.replace(token, "")
        return action_reply(
            "",
            {"type": "complete_task", "task_query": _normalize_task_query_text(task_query)},
        )

    if normalized.lower().startswith(("delete task:", "remove task:", "drop task:", "delete ", "remove ", "drop ")) or any(
        token in normalized for token in ["删掉", "删除", "去掉", "移除"]
    ):
        task_query = normalized
        for token in ["帮我", "把", "吧", "删掉", "删除", "去掉", "移除", "delete task:", "remove task:", "drop task:", "delete ", "remove ", "drop "]:
            task_query = task_query.replace(token, "")
        return action_reply(
            "",
            {"type": "delete_task", "task_query": _normalize_task_query_text(task_query)},
        )

    if normalized.lower().startswith(("defer task:", "postpone task:", "defer ", "postpone ")) or any(
        token in normalized for token in ["延后", "推迟", "稍后再做"]
    ):
        task_query = normalized
        for token in ["帮我", "把", "吧", "延后", "推迟", "稍后再做", "defer task:", "postpone task:", "defer ", "postpone "]:
            task_query = task_query.replace(token, "")
        due_date = _extract_due_date_hint(normalized)
        return action_reply(
            "",
            {"type": "defer_task", "task_query": _strip_due_hint(_normalize_task_query_text(task_query)), "due_date": due_date},
        )

    if (normalized.lower().startswith(("mark temporary:", "mark as temporary:", "mark ")) and "temporary" in lower) or any(
        token in normalized for token in ["标成临时", "改成临时", "临时任务"]
    ):
        task_query = normalized
        for token in ["帮我", "把", "吧", "标成临时", "改成临时", "临时任务", "mark temporary:", "mark as temporary:", "mark ", "as temporary"]:
            task_query = task_query.replace(token, "")
        return action_reply(
            "",
            {"type": "update_task", "task_query": _normalize_task_query_text(task_query), "task_kind": "temporary"},
        )

    if (normalized.lower().startswith(("mark daily:", "mark as daily:", "mark ")) and "daily" in lower) or any(
        token in normalized for token in ["标成每日", "改成每日", "日常任务", "每天任务"]
    ):
        task_query = normalized
        for token in ["帮我", "把", "吧", "标成每日", "改成每日", "日常任务", "每天任务", "mark daily:", "mark as daily:", "mark ", "as daily"]:
            task_query = task_query.replace(token, "")
        return action_reply(
            "",
            {"type": "update_task", "task_query": _normalize_task_query_text(task_query), "task_kind": "daily"},
        )

    if _extract_due_date_hint(normalized) and (
        any(token in normalized for token in ["ddl", "截止", "到期", "due", "设置到", "设到", "改到", "调到", "安排到"])
        or any(token in lower for token in ["deadline", "due date", "set to", "move to", "schedule for"])
    ):
        task_query = _extract_due_date_update_query(normalized)
        if not task_query:
            task_query = normalized
            for token in [
                "帮我", "把", "吧", "的ddl", "ddl", "截止日期", "截止时间", "截止", "到期时间", "到期", "due date", "deadline", "due",
                "设置到", "设到", "改到", "调到", "安排到", "set to", "move to", "schedule for",
            ]:
                task_query = task_query.replace(token, "")
        return action_reply(
            "",
            {
                "type": "update_task",
                "task_query": _strip_due_hint(_normalize_task_query_text(task_query)),
                "due_date": _extract_due_date_hint(normalized),
            },
        )

    if "mood" in lower or "feel" in lower or any(token in normalized for token in ["心情", "状态", "感觉"]):
        for level, hints in ((1, ["很糟", "崩", "terrible", "awful"]), (2, ["不太好", "低落", "bad", "down"]), (3, ["一般", "还行", "okay", "fine"]), (4, ["不错", "good"]), (5, ["超棒", "很好", "great", "amazing"])):
            if any(hint in lower or hint in normalized for hint in hints):
                return action_reply(
                    "",
                    {"type": "log_mood", "mood_level": level, "note": normalized},
                )

    if allow_natural_language_fast_paths and re.match(r"^(我要|我想|我得|我需要|今天要|等会要)\s*\S+", normalized):
        title = _strip_due_hint(_canonical_task_text(normalized))
        if title:
            due_date = _extract_due_date_hint(normalized) or _extract_plain_weekday_due_date(normalized)
            return action_reply(
                "",
                {"type": "add_task", "title": title, "description": "", "priority": 0, "due_date": due_date},
            )

    if allow_natural_language_fast_paths and re.match(r"^(i need to|i have to|i should|i want to)\s+\S+", lower):
        title = re.sub(r"^(i need to|i have to|i should|i want to)\s+", "", normalized, flags=re.IGNORECASE).strip()
        title = _strip_due_hint(_canonical_task_text(title))
        if title:
            due_date = _extract_due_date_hint(normalized) or _extract_plain_weekday_due_date(normalized)
            return action_reply(
                "",
                {"type": "add_task", "title": title, "description": "", "priority": 0, "due_date": due_date},
            )

    recurring_daily_zh = re.match(r"^(?:我)?(?:每天|每日|每天都|每日都)\s*(?:要|得|需要|会)?\s*(.+)$", normalized)
    if allow_natural_language_fast_paths and not _looks_like_question(message) and recurring_daily_zh:
        title = _canonical_task_text(recurring_daily_zh.group(1))
        if title:
            return action_reply(
                "",
                {
                    "type": "add_task",
                    "title": title,
                    "description": "",
                    "priority": 0,
                    "due_date": None,
                    "task_kind": "daily",
                },
            )

    recurring_daily_en = (
        re.match(r"^(?:i\s+)?(?:every day|daily)\s+(.+)$", normalized, flags=re.IGNORECASE)
        or re.match(r"^(?:i\s+)?(.+?)\s+every day$", normalized, flags=re.IGNORECASE)
    )
    if allow_natural_language_fast_paths and not _looks_like_question(message) and recurring_daily_en:
        title = _canonical_task_text(recurring_daily_en.group(1))
        if title:
            return action_reply(
                "",
                {
                    "type": "add_task",
                    "title": title,
                    "description": "",
                    "priority": 0,
                    "due_date": None,
                    "task_kind": "daily",
                },
            )

    recurring_en = re.match(
        r"^i\s+have\s+(?:a\s+)?plans?\s+(?:on\s+)?every\s+(.+?)\s+to\s+(.+)$",
        normalized,
        flags=re.IGNORECASE,
    )
    if allow_natural_language_fast_paths and recurring_en:
        weekdays = _extract_all_recurrence_weekdays(recurring_en.group(1))
        title = _canonical_task_text(recurring_en.group(2))
        if title:
            if len(weekdays) > 1:
                return _build_action_reply(
                    "",
                    [
                        {
                            "type": "add_task",
                            "title": title,
                            "description": "",
                            "priority": 0,
                            "due_date": None,
                            "task_kind": "weekly",
                            "recurrence_weekday": weekday,
                        }
                        for weekday in weekdays
                    ],
                )
            return action_reply(
                "",
                {
                    "type": "add_task",
                    "title": title,
                    "description": "",
                    "priority": 0,
                    "due_date": None,
                    "task_kind": "weekly",
                    "recurrence_weekday": weekdays[0] if weekdays else infer_recurrence_weekday(normalized),
                },
            )

    relative_weekday_zh = re.match(r"^(我)?(?:(?:这|本|下|下下)周|(?:这|本|下|下下)星期)([一二三四五六日天12345670]).*(.+)$", normalized)
    if allow_natural_language_fast_paths and not _looks_like_question(message) and relative_weekday_zh:
        title = _canonical_task_text(re.sub(r"^我", "", normalized, count=1))
        if title:
            due_date = _extract_due_date_hint(normalized) or upcoming_weekday_iso(infer_recurrence_weekday(normalized) or 0)
            return action_reply(
                "",
                {
                    "type": "add_task",
                    "title": title,
                    "description": "",
                    "priority": 0,
                    "due_date": due_date,
                },
            )

    recurring_zh = re.match(r"^(我)?(?:每周|每星期|每礼拜|周|星期|礼拜)([一二三四五六日天12345670]).*(.+)$", normalized)
    if allow_natural_language_fast_paths and not _looks_like_question(message) and recurring_zh:
        title = _canonical_task_text(re.sub(r"^我", "", normalized, count=1))
        if title:
            return action_reply(
                "",
                {
                    "type": "add_task",
                    "title": title,
                    "description": "",
                    "priority": 0,
                    "due_date": None,
                    "task_kind": "weekly",
                    "recurrence_weekday": infer_recurrence_weekday(normalized),
                },
            )

    if allow_natural_language_fast_paths and (
        re.match(r"^(帮我|给我|请|麻烦你)?\s*(加上|加入|添加|新增|加个|加一个|加一项|记录一下)", normalized)
        or re.match(r"^(add|create)\s+((a|an)\s+)?", lower)
    ):
        title = _normalize_task_title_text(normalized)
        if title:
            return action_reply(
                "",
                {"type": "add_task", "title": title, "description": "", "priority": 0, "due_date": None},
            )

    if allow_natural_language_fast_paths and (
        normalized.lower().startswith(("add ", "add task", "task:"))
        or normalized.startswith(("帮我加", "帮我添加", "帮我新增", "给我加", "给我添加", "加一个", "添加一个", "新增一个"))
    ):
        title = normalized
        lower_title = lower
        prefix_map = [
            ("add task:", len("add task:")),
            ("add task", len("add task")),
            ("task:", len("task:")),
            ("add ", len("add ")),
        ]
        matched_prefix = next((length for prefix, length in prefix_map if lower_title.startswith(prefix)), None)
        if matched_prefix is not None:
            title = normalized[matched_prefix:]
        for token in ["帮我", "给我", "加一个任务", "添加任务", "新增任务", "任务：", "任务:", "加上", "添加", "新增"]:
            title = title.replace(token, "")
        title = re.sub(r"^(一个任务|一个|一项|一条)\s*", "", title.strip())
        title = re.sub(r"^(a|an)\s+", "", title.strip(), flags=re.IGNORECASE)
        title = re.sub(r"的任务$", "", title.strip())
        return action_reply(
            "",
            {"type": "add_task", "title": title.strip(" ：:，,." ) or normalized, "description": "", "priority": 0, "due_date": None},
        )

    if llm_available:
        parsed = _try_llm_assistant_reply(llm, message, lang, profile, history, ctx)
        if parsed:
            for action in parsed.get("actions", []):
                if action.get("type") == "add_task":
                    if not action.get("task_kind"):
                        action["task_kind"] = infer_task_kind(
                            message,
                            action.get("description") or "",
                            action.get("due_date"),
                            None,
                        )
                    if action.get("task_kind") == "weekly" and action.get("recurrence_weekday") is None:
                        action["recurrence_weekday"] = infer_recurrence_weekday(
                            message,
                            action.get("description") or "",
                        )
            return parsed
    return {
        "reply": "我理解了。你继续说，我可以帮你改任务、调计划、或者先帮你澄清模糊事项。" if lang == "zh" else "Understood. Keep going and I can adjust tasks, update plans, or clarify fuzzy items.",
        "requires_clarification": False,
        "clarification_question": "",
        "actions": [],
    }


def _select_task_from_message(message: str, matches: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    cleaned = message.strip().lower()
    compact_cleaned = _compact_task_text(message)
    if cleaned.isdigit():
        index = int(cleaned) - 1
        if 0 <= index < len(matches):
            return matches[index]
    ordinal_map = {"first": 0, "1": 0, "第一个": 0, "第1个": 0, "second": 1, "2": 1, "第二个": 1, "第2个": 1}
    for key, index in ordinal_map.items():
        if key in message.lower() and index < len(matches):
            return matches[index]
    for item in matches:
        if item["title"].lower() in cleaned:
            return item
        if compact_cleaned and _compact_task_text(item["title"]) == compact_cleaned:
            return item
    return None


def _resolve_task_query(tasks: List[Task], query: str) -> Dict[str, Any]:
    normalized = (query or "").strip().lower()
    canonical_query = _canonical_task_text(query)
    compact_query = _compact_task_text(query)
    semantic_query = _semantic_task_key(query)
    exact = [
        task for task in tasks
        if task.title.strip().lower() == normalized or _canonical_task_text(task.title) == canonical_query
    ]
    if not exact and compact_query:
        exact = [
            task for task in tasks
            if _compact_task_text(task.title) == compact_query
        ]
    if len(exact) == 1:
        return {"status": "ok", "task": exact[0]}
    if not exact and semantic_query:
        semantic = [
            task for task in tasks
            if _semantic_task_key(task.title) == semantic_query
        ]
        if len(semantic) == 1:
            return {"status": "ok", "task": semantic[0]}
        if len(semantic) > 1:
            return {
                "status": "ambiguous",
                "matches": [{"id": task.id, "title": task.title} for task in semantic[:5]],
            }
    partial = [
        task for task in tasks
        if (
            normalized and normalized in task.title.strip().lower()
        ) or (
            canonical_query and canonical_query in _canonical_task_text(task.title)
        ) or (
            compact_query and compact_query in _compact_task_text(task.title)
        ) or (
            semantic_query and semantic_query in _semantic_task_key(task.title)
        )
    ]
    if len(partial) == 1:
        return {"status": "ok", "task": partial[0]}
    if len(exact) > 1 or len(partial) > 1:
        candidates = exact if len(exact) > 1 else partial
        return {
            "status": "ambiguous",
            "matches": [{"id": task.id, "title": task.title} for task in candidates[:5]],
        }
    return {"status": "missing"}


def _find_existing_active_task(
    tasks: List[Task],
    title: str,
    task_kind: str | None = None,
    recurrence_weekday: int | None = None,
) -> Task | None:
    canonical_title = _canonical_task_text(title)
    normalized_title = (title or "").strip().lower()
    if not canonical_title and not normalized_title:
        return None
    for task in tasks:
        if task_kind == "weekly" and recurrence_weekday is not None:
            if task.task_kind != "weekly" or task.recurrence_weekday != recurrence_weekday:
                continue
        task_normalized = task.title.strip().lower()
        task_canonical = _canonical_task_text(task.title)
        if normalized_title and task_normalized == normalized_title:
            return task
        if canonical_title and task_canonical == canonical_title:
            return task
    return None


def _history(db, task_id: int, action: str, reasoning: str) -> None:
    db.add(
        TaskHistory(
            task_id=task_id,
            date=local_today_iso(),
            action=action,
            ai_reasoning=reasoning,
        )
    )


def _execute_plan_regeneration(db, user_id: int, lang: str) -> str:
    today = local_today_iso()
    storage_key = plan_storage_key(user_id, today)
    existing = db.query(DailyPlan).filter(DailyPlan.date == storage_key).first()
    if existing:
        db.delete(existing)
        db.flush()
    tasks = (
        db.query(Task)
        .filter(Task.user_id == user_id, Task.status == TaskStatus.ACTIVE.value)
        .order_by(Task.priority.desc(), Task.created_at.asc())
        .all()
    )
    if not tasks:
        return "没有可用于规划的活跃任务。" if lang == "zh" else "There are no active tasks to plan."
    result = generate_daily_plan(tasks, today, lang=lang)
    plan = DailyPlan(
        date=storage_key,
        reasoning=result["reasoning"],
        overload_warning=result.get("overload_warning", ""),
        max_tasks=result.get("max_tasks", 4),
    )
    db.add(plan)
    db.flush()
    for index, selected in enumerate(result.get("selected_tasks", [])):
        db.add(PlanTask(plan_id=plan.id, task_id=selected["task_id"], status=PlanTaskStatus.PLANNED.value, order=index))
        _history(db, selected["task_id"], HistoryAction.PLANNED.value, selected.get("reason", "Planned by concierge."))
    db.flush()
    return "今天的计划已经更新。" if lang == "zh" else "Today's plan has been refreshed."


def _execute_actions(db, user, actions: List[Dict[str, Any]], lang: str) -> Dict[str, Any]:
    summaries: List[str] = []
    pending: Dict[str, Any] = dict(DEFAULT_PENDING)
    context = _user_context(db, user.id)
    active_tasks = context["active_tasks"]

    for action in actions:
        action_type = action.get("type", "")
        if action_type == "add_task":
            title = _normalize_task_title_text(action.get("title") or "")
            normalized_due_date = (
                normalize_date_string(action.get("due_date"))
                or infer_relative_due_date(title, action.get("description") or "")
            )
            explicit_kind = action.get("task_kind")
            if normalized_due_date and explicit_kind == "weekly":
                explicit_kind = None
            inferred_kind = infer_task_kind(title, action.get("description") or "", normalized_due_date, explicit_kind)
            inferred_weekday = (
                infer_recurrence_weekday(
                    title,
                    action.get("description") or "",
                    action.get("recurrence_weekday"),
                )
                if inferred_kind == "weekly"
                else None
            )
            if not title:
                pending = {
                    "type": "llm_followup",
                    "data": {"message": "add task", "question": "请告诉我你想添加的任务标题。" if lang == "zh" else "What task should I add?"},
                }
                break
            existing_task = _find_existing_active_task(active_tasks, title, inferred_kind, inferred_weekday)
            if existing_task:
                if normalized_due_date:
                    existing_task.due_date = normalized_due_date
                if action.get("task_kind"):
                    existing_task.task_kind = action["task_kind"]
                summaries.append(
                    (f"任务已存在：{existing_task.title}" if lang == "zh" else f"Task already exists: {existing_task.title}")
                )
                active_tasks = _user_context(db, user.id)["active_tasks"]
                continue
            task = Task(
                user_id=user.id,
                title=strip_task_kind_markers(title)[0],
                description=(action.get("description") or "").strip(),
                priority=int(action.get("priority") or 0),
                status=TaskStatus.ACTIVE.value,
                source="manual",
                task_kind=inferred_kind,
                recurrence_weekday=inferred_weekday,
                decision_reason="Created by concierge.",
                due_date=normalized_due_date,
            )
            db.add(task)
            db.flush()
            _history(db, task.id, HistoryAction.CREATED.value, "Task created by concierge.")
            summaries.append(f"已添加任务：{task.title}" if lang == "zh" else f"Added task: {task.title}")
            active_tasks = _user_context(db, user.id)["active_tasks"]
        elif action_type in {"delete_task", "update_task", "complete_task", "defer_task"}:
            resolution = _resolve_task_query(active_tasks, action.get("task_query", ""))
            if resolution["status"] == "missing":
                pending = {
                    "type": "llm_followup",
                    "data": {
                        "message": json.dumps(action, ensure_ascii=False),
                        "question": "我还没定位到你说的是哪个任务，你能把任务名说得更具体一点吗？" if lang == "zh" else "I couldn't identify the task yet. Could you name it more specifically?",
                    },
                }
                break
            if resolution["status"] == "ambiguous":
                labels = "\n".join(f'{index + 1}. {item["title"]}' for index, item in enumerate(resolution["matches"]))
                pending = {
                    "type": "task_choice",
                    "data": {"action": action, "matches": resolution["matches"]},
                }
                summaries.append(
                    ("我找到多个可能的任务，请回复编号或更具体的名字：\n" + labels)
                    if lang == "zh"
                    else ("I found multiple matching tasks. Reply with a number or a more specific title:\n" + labels)
                )
                break
            task = resolution["task"]
            if action_type == "delete_task":
                task.status = TaskStatus.DELETED.value
                task.deleted_at = datetime.now(timezone.utc)
                _history(db, task.id, HistoryAction.DELETED.value, "Task deleted by concierge.")
                summaries.append(f"已删除任务：{task.title}" if lang == "zh" else f"Deleted task: {task.title}")
            elif action_type == "complete_task":
                task.status = TaskStatus.COMPLETED.value
                task.completed_at = datetime.now(timezone.utc)
                task.completion_count += 1
                _history(db, task.id, HistoryAction.COMPLETED.value, "Task completed by concierge.")
                summaries.append(f"已完成任务：{task.title}" if lang == "zh" else f"Completed task: {task.title}")
            elif action_type == "defer_task":
                task.deferral_count += 1
                task.due_date = normalize_date_string(action.get("due_date")) or local_date_offset_iso(1)
                _history(
                    db,
                    task.id,
                    HistoryAction.DEFERRED.value,
                    (
                        f"任务已被私人管家推迟到 {task.due_date}。"
                        if lang == "zh"
                        else f"Task deferred by concierge to {task.due_date}."
                    ),
                )
                summaries.append(
                    (f"已延后任务：{task.title} → {task.due_date}" if lang == "zh" else f"Deferred task: {task.title} -> {task.due_date}")
                )
            elif action_type == "update_task":
                title_changed = bool(action.get("title"))
                if action.get("title"):
                    task.title = action["title"].strip()
                if action.get("description") is not None:
                    task.description = action["description"].strip()
                if action.get("task_kind") is not None:
                    task.task_kind = action["task_kind"]
                if action.get("priority") is not None:
                    task.priority = int(action["priority"])
                if action.get("due_date") is not None:
                    task.due_date = normalize_date_string(action["due_date"])
                task.recurrence_weekday = (
                    infer_recurrence_weekday(task.title, task.description, None if title_changed else task.recurrence_weekday)
                    if task.task_kind == "weekly"
                    else None
                )
                summaries.append(f"已更新任务：{task.title}" if lang == "zh" else f"Updated task: {task.title}")
            active_tasks = _user_context(db, user.id)["active_tasks"]
        elif action_type == "generate_plan":
            summaries.append(_execute_plan_regeneration(db, user.id, lang))
        elif action_type == "log_mood":
            try:
                mood_level = int(action.get("mood_level") or 0)
            except (ValueError, TypeError):
                mood_level = 0
            if 1 <= mood_level <= 5:
                db.add(MoodEntry(user_id=user.id, date=local_today_iso(), mood_level=mood_level, note=(action.get("note") or "").strip()))
                summaries.append("已记录心情。" if lang == "zh" else "Mood logged.")
    db.flush()
    return {"summaries": summaries, "pending": pending}


@router.get("/state")
def get_assistant_state(request: Request, lang: str = "en"):
    with get_db() as db:
        user = require_current_user(db, request)
        profile = _coerce_profile(read_setting(db, _profile_key(user.id), DEFAULT_PROFILE))
        history = read_setting(db, _history_key(user.id), DEFAULT_HISTORY)
        pending = read_setting(db, _pending_key(user.id), DEFAULT_PENDING)
        history = _ensure_profile_prompt(profile, history, lang)
        write_setting(db, _profile_key(user.id), profile)
        write_setting(db, _history_key(user.id), history)
        return _assistant_state(profile, history, pending, lang)


@router.post("/chat")
def chat_with_assistant(payload: AssistantChatRequest, request: Request):
    with get_db() as db:
        user = require_current_user(db, request)
        profile = _coerce_profile(read_setting(db, _profile_key(user.id), DEFAULT_PROFILE))
        history = read_setting(db, _history_key(user.id), DEFAULT_HISTORY)
        pending = read_setting(db, _pending_key(user.id), DEFAULT_PENDING)
        history = _ensure_profile_prompt(profile, history, payload.lang)
        message = payload.message.strip()
        history = _push_message(history, "user", message)
        if pending.get("type") and _looks_like_fresh_request(message):
            pending = dict(DEFAULT_PENDING)
            write_setting(db, _pending_key(user.id), pending)

        if pending.get("type") == "task_choice":
            chosen = _select_task_from_message(message, pending.get("data", {}).get("matches", []))
            if chosen:
                action = dict(pending.get("data", {}).get("action", {}))
                action["task_query"] = chosen["title"]
                result = _execute_actions(db, user, [action], payload.lang)
                assistant_reply = "\n".join(result["summaries"]) or ("好的，已经处理。" if payload.lang == "zh" else "Done.")
                history = _push_message(history, "assistant", assistant_reply)
                write_setting(db, _pending_key(user.id), result["pending"])
            else:
                history = _push_message(
                    history,
                    "assistant",
                    "我还没能确定是哪一个，请回复数字编号，或者把任务名说得更完整一点。" if payload.lang == "zh" else "I still can't tell which one you mean. Reply with the number or a more complete task name.",
                )
            write_setting(db, _history_key(user.id), history)
            return _assistant_state(profile, history, read_setting(db, _pending_key(user.id), DEFAULT_PENDING), payload.lang)

        if pending.get("type") == "llm_followup":
            original = pending.get("data", {}).get("message", "")
            structured_action = None
            if isinstance(original, str) and original.strip().startswith("{"):
                try:
                    maybe_action = json.loads(original)
                    if isinstance(maybe_action, dict) and maybe_action.get("type") in {"add_task", "delete_task", "update_task", "complete_task", "defer_task"}:
                        structured_action = maybe_action
                except Exception:
                    structured_action = None
            if structured_action:
                if structured_action.get("type") == "add_task":
                    structured_action["title"] = message.strip()
                else:
                    structured_action["task_query"] = message.strip()
                parsed = {"reply": "", "requires_clarification": False, "clarification_question": "", "actions": [structured_action]}
            else:
                parsed = _call_assistant_llm(f"{original}\nClarification: {message}", payload.lang, profile, history, _user_context(db, user))
        else:
            parsed = _call_assistant_llm(message, payload.lang, profile, history, _user_context(db, user))

        if parsed.get("requires_clarification"):
            next_pending = {
                "type": "llm_followup",
                "data": {"message": message, "question": parsed.get("clarification_question", "")},
            }
            question = parsed.get("clarification_question") or parsed.get("reply") or (
                "我还需要你补充一点信息。" if payload.lang == "zh" else "I need a bit more detail."
            )
            history = _push_message(history, "assistant", question)
            write_setting(db, _pending_key(user.id), next_pending)
            write_setting(db, _history_key(user.id), history)
            return _assistant_state(profile, history, next_pending, payload.lang)

        execution = _execute_actions(db, user, parsed.get("actions", []), payload.lang)
        reply_parts = []
        if parsed.get("reply"):
            cleaned_reply = _sanitize_assistant_text(parsed["reply"])
            if cleaned_reply:
                reply_parts.append(cleaned_reply)
        reply_parts.extend(execution["summaries"])
        if execution["pending"].get("type") == "llm_followup":
            followup_question = execution["pending"].get("data", {}).get("question", "")
            if followup_question:
                reply_parts.append(followup_question)
        elif execution["pending"].get("type") == "task_choice" and execution["summaries"]:
            pass
        assistant_reply = "\n".join(part for part in reply_parts if part).strip() or (
            "好的，我已经处理。" if payload.lang == "zh" else "Done."
        )
        history = _push_message(history, "assistant", assistant_reply)
        write_setting(db, _profile_key(user.id), profile)
        write_setting(db, _pending_key(user.id), execution["pending"])
        write_setting(db, _history_key(user.id), history)
        return _assistant_state(profile, history, execution["pending"], payload.lang)
