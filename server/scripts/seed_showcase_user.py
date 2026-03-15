from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Keep seed data aligned with the running local server DB even when the script is
# executed from the repository root.
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(ROOT / 'deletion_planner.db').resolve()}")

from api_v2.routers.assistant import DEFAULT_HISTORY, DEFAULT_PENDING, DEFAULT_PROFILE
from api_v2.user_context import onboarding_key, plan_storage_key
from core.showcase import load_protected_showcase_usernames, save_protected_showcase_usernames
from core.time import local_today
from database.db import get_db, init_db
from database.models import (
    AppSetting,
    DailyFortune,
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
    UserSession,
)

SHOWCASE_USERNAME = "chen"
SHOWCASE_PASSWORD = "123456"
SHOWCASE_BIRTHDAY = "2002-10-12"
SHOWCASE_GENDER = "prefer_not_to_say"


def stamp(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour=hour, minute=minute), tzinfo=timezone.utc)


def upsert_json_setting(db, key: str, payload: dict) -> None:
    value = json.dumps(payload, ensure_ascii=False)
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    db.flush()


def clear_showcase_user_state(db, user_id: int) -> None:
    db.query(UserSession).filter(UserSession.user_id == user_id).delete(synchronize_session=False)
    db.query(MoodEntry).filter(MoodEntry.user_id == user_id).delete(synchronize_session=False)
    db.query(DailyFortune).filter(DailyFortune.user_id == user_id).delete(synchronize_session=False)
    db.query(FocusSession).filter(FocusSession.user_id == user_id).delete(synchronize_session=False)

    task_ids = [row.id for row in db.query(Task.id).filter(Task.user_id == user_id).all()]
    if task_ids:
        db.query(TaskHistory).filter(TaskHistory.task_id.in_(task_ids)).delete(synchronize_session=False)
        db.query(Task).filter(Task.id.in_(task_ids)).delete(synchronize_session=False)

    plan_ids = [
        row.id
        for row in db.query(DailyPlan.id, DailyPlan.date).all()
        if str(row.date).startswith(f"{user_id}:")
    ]
    if plan_ids:
        db.query(PlanTask).filter(PlanTask.plan_id.in_(plan_ids)).delete(synchronize_session=False)
        db.query(DailyPlan).filter(DailyPlan.id.in_(plan_ids)).delete(synchronize_session=False)

    prefixes = [
        f"prototype_onboarding:{user_id}",
        f"assistant_profile:{user_id}",
        f"assistant_history:{user_id}",
        f"assistant_pending:{user_id}",
    ]
    db.query(AppSetting).filter(AppSetting.key.in_(prefixes)).delete(synchronize_session=False)
    db.flush()


def add_history(db, task: Task, day: date, action: str, reasoning: str, hour: int, minute: int = 0) -> None:
    db.add(
        TaskHistory(
            task_id=task.id,
            date=day.isoformat(),
            action=action,
            ai_reasoning=reasoning,
            created_at=stamp(day, hour, minute),
        )
    )


def add_mood_entries(db, user_id: int, day: date, entries: list[tuple[int, str, int, int]]) -> None:
    for mood_level, note, hour, minute in entries:
        db.add(
            MoodEntry(
                user_id=user_id,
                date=day.isoformat(),
                mood_level=mood_level,
                note=note,
                created_at=stamp(day, hour, minute),
            )
        )


def add_task(
    db,
    *,
    user_id: int,
    title: str,
    created_day: date,
    priority: int = 0,
    sort_order: int = 0,
    task_kind: str = "temporary",
    recurrence_weekday: int | None = None,
    due_date: str | None = None,
    description: str = "",
    status: str = TaskStatus.ACTIVE.value,
    source: str = "ai",
    decision_reason: str = "",
    deferral_count: int = 0,
    completion_count: int = 0,
    completed_day: date | None = None,
    deleted_day: date | None = None,
) -> Task:
    task = Task(
        user_id=user_id,
        title=title,
        description=description,
        priority=priority,
        sort_order=sort_order,
        task_kind=task_kind,
        recurrence_weekday=recurrence_weekday,
        due_date=due_date,
        status=status,
        source=source,
        decision_reason=decision_reason,
        deferral_count=deferral_count,
        completion_count=completion_count,
        created_at=stamp(created_day, 9, 0),
        updated_at=stamp(completed_day or deleted_day or created_day, 18, 0),
        completed_at=stamp(completed_day, 18, 15) if completed_day else None,
        deleted_at=stamp(deleted_day, 17, 40) if deleted_day else None,
    )
    db.add(task)
    db.flush()
    add_history(db, task, created_day, HistoryAction.CREATED.value, "Task created by user.", 9, 5)
    return task


def create_plan(db, user_id: int, day: date, picks: list[tuple[Task, str, str]]) -> None:
    plan = DailyPlan(
        date=plan_storage_key(user_id, day.isoformat()),
        reasoning="Balanced around school, work, and recovery.",
        overload_warning="",
        max_tasks=max(4, len(picks)),
        created_at=stamp(day, 7, 30),
    )
    db.add(plan)
    db.flush()
    for index, (task, status, reason) in enumerate(picks):
        db.add(
            PlanTask(
                plan_id=plan.id,
                task_id=task.id,
                status=status,
                order=index,
            )
        )
        add_history(db, task, day, HistoryAction.PLANNED.value, reason, 7, 45 + index)


def main() -> None:
    init_db()
    today = local_today()

    with get_db() as db:
        protected = load_protected_showcase_usernames(db)
        protected.add(SHOWCASE_USERNAME)
        save_protected_showcase_usernames(db, protected)

        user = db.query(User).filter(User.username == SHOWCASE_USERNAME).first()
        if not user:
            user = User(
                username=SHOWCASE_USERNAME,
                password=SHOWCASE_PASSWORD,
                birthday=SHOWCASE_BIRTHDAY,
                gender=SHOWCASE_GENDER,
                created_at=stamp(today - timedelta(days=78), 10, 0),
            )
            db.add(user)
            db.flush()
        else:
            user.password = SHOWCASE_PASSWORD
            user.birthday = SHOWCASE_BIRTHDAY
            user.gender = SHOWCASE_GENDER

        clear_showcase_user_state(db, user.id)

        if not user.created_at:
            user.created_at = stamp(today - timedelta(days=78), 10, 0)

        # Recurring tasks
        water = add_task(
            db,
            user_id=user.id,
            title="Drink 2L of water",
            created_day=today - timedelta(days=65),
            priority=2,
            sort_order=10,
            task_kind="daily",
            description="Keep energy steady through classes and shift work.",
            decision_reason="Recurring health habit kept visible.",
            deferral_count=4,
            completion_count=41,
        )
        walk = add_task(
            db,
            user_id=user.id,
            title="Take a 20-minute walk",
            created_day=today - timedelta(days=62),
            priority=2,
            sort_order=20,
            task_kind="daily",
            description="Usually after lunch or before sunset.",
            decision_reason="Low-friction habit for recovery.",
            deferral_count=5,
            completion_count=36,
        )
        journal = add_task(
            db,
            user_id=user.id,
            title="Write a short journal entry",
            created_day=today - timedelta(days=56),
            priority=1,
            sort_order=30,
            task_kind="daily",
            description="A few lines before bed.",
            decision_reason="End-of-day reflection anchor.",
            deferral_count=7,
            completion_count=28,
        )
        cook = add_task(
            db,
            user_id=user.id,
            title="Cook dinner at home",
            created_day=today - timedelta(days=49),
            priority=2,
            sort_order=40,
            task_kind="daily",
            description="Used to reduce late takeout spending.",
            decision_reason="Daily routine that saves money and lowers stress.",
            deferral_count=6,
            completion_count=31,
        )
        cafe = add_task(
            db,
            user_id=user.id,
            title="Tuesday cafe shift",
            created_day=today - timedelta(days=54),
            priority=4,
            sort_order=50,
            task_kind="weekly",
            recurrence_weekday=1,
            description="Part-time shift from 3pm to 8pm.",
            decision_reason="Protected weekly work commitment.",
            completion_count=7,
        )
        critique = add_task(
            db,
            user_id=user.id,
            title="Thursday design critique",
            created_day=today - timedelta(days=44),
            priority=4,
            sort_order=60,
            task_kind="weekly",
            recurrence_weekday=3,
            description="Studio feedback session with classmates.",
            decision_reason="High-leverage recurring school event.",
            completion_count=6,
        )
        parents = add_task(
            db,
            user_id=user.id,
            title="Friday call parents",
            created_day=today - timedelta(days=52),
            priority=2,
            sort_order=70,
            task_kind="weekly",
            recurrence_weekday=4,
            description="Usually a 25-minute check-in after dinner.",
            decision_reason="Relationship maintenance routine.",
            completion_count=7,
        )
        reset = add_task(
            db,
            user_id=user.id,
            title="Sunday reset and laundry",
            created_day=today - timedelta(days=39),
            priority=3,
            sort_order=80,
            task_kind="weekly",
            recurrence_weekday=6,
            description="Reset room, laundry, and prep for Monday.",
            decision_reason="Weekly reset block.",
            deferral_count=1,
            completion_count=4,
        )

        # Upcoming active tasks
        capstone = add_task(
            db,
            user_id=user.id,
            title="Finish capstone slides",
            created_day=today - timedelta(days=18),
            priority=5,
            sort_order=90,
            due_date=(today + timedelta(days=3)).isoformat(),
            description="Need a cleaner story arc and final numbers.",
            decision_reason="Core school deliverable for next week.",
            deferral_count=2,
            completion_count=0,
        )
        follow_up = add_task(
            db,
            user_id=user.id,
            title="Send internship follow-up",
            created_day=today - timedelta(days=12),
            priority=4,
            sort_order=100,
            due_date=(today + timedelta(days=4)).isoformat(),
            description="Follow up after the product design interview.",
            decision_reason="Time-sensitive communication task.",
            deferral_count=1,
        )
        birthday = add_task(
            db,
            user_id=user.id,
            title="Book birthday dinner for Maya",
            created_day=today - timedelta(days=9),
            priority=3,
            sort_order=110,
            due_date=(today + timedelta(days=6)).isoformat(),
            description="Find a cozy place near campus and make a reservation.",
            decision_reason="Personal commitment with a fixed date.",
        )
        license_task = add_task(
            db,
            user_id=user.id,
            title="Renew driver's license",
            created_day=today - timedelta(days=15),
            priority=2,
            sort_order=120,
            due_date=(today + timedelta(days=14)).isoformat(),
            description="Gather documents and book DMV time slot.",
            decision_reason="Important but not urgent admin task.",
            deferral_count=2,
        )

        # Completed tasks
        reflection = add_task(
            db,
            user_id=user.id,
            title="Submit product reflection",
            created_day=today - timedelta(days=23),
            priority=4,
            sort_order=130,
            due_date=(today - timedelta(days=10)).isoformat(),
            description="Weekly product strategy write-up.",
            status=TaskStatus.COMPLETED.value,
            decision_reason="Closed school deliverable.",
            completion_count=1,
            completed_day=today - timedelta(days=10),
        )
        tickets = add_task(
            db,
            user_id=user.id,
            title="Buy Boston train tickets",
            created_day=today - timedelta(days=20),
            priority=2,
            sort_order=140,
            due_date=(today - timedelta(days=7)).isoformat(),
            description="Spring break logistics.",
            status=TaskStatus.COMPLETED.value,
            decision_reason="Finished travel booking.",
            completion_count=1,
            completed_day=today - timedelta(days=7),
        )
        portfolio = add_task(
            db,
            user_id=user.id,
            title="Fix portfolio footer",
            created_day=today - timedelta(days=14),
            priority=3,
            sort_order=150,
            due_date=(today - timedelta(days=5)).isoformat(),
            description="Clean up alignment and update contact links.",
            status=TaskStatus.COMPLETED.value,
            decision_reason="Quick polish task already finished.",
            completion_count=1,
            completed_day=today - timedelta(days=5),
        )

        # Deleted tasks
        club = add_task(
            db,
            user_id=user.id,
            title="Join another club",
            created_day=today - timedelta(days=27),
            priority=0,
            sort_order=160,
            description="Looked exciting but not realistic this semester.",
            status=TaskStatus.DELETED.value,
            decision_reason="Explicitly dropped to protect capacity.",
            deleted_day=today - timedelta(days=19),
        )
        gym = add_task(
            db,
            user_id=user.id,
            title="Cancel old gym membership",
            created_day=today - timedelta(days=32),
            priority=1,
            sort_order=170,
            description="Old membership still auto-renewed.",
            status=TaskStatus.DELETED.value,
            decision_reason="Closed after deciding to switch to walking outside.",
            deleted_day=today - timedelta(days=21),
        )

        # Additional history to make the account feel lived-in.
        for offset in range(14, 0, -1):
            day = today - timedelta(days=offset)
            add_history(db, water, day, HistoryAction.COMPLETED.value, "Task completed by user.", 21, 5)
            if offset % 3 != 0:
                add_history(db, walk, day, HistoryAction.COMPLETED.value, "Task completed by user.", 19, 20)
            else:
                add_history(
                    db,
                    walk,
                    day,
                    HistoryAction.DEFERRED.value,
                    f"Task deferred to {(day + timedelta(days=1)).isoformat()} by user.",
                    18,
                    40,
                )
            if offset % 2 == 0:
                add_history(db, journal, day, HistoryAction.COMPLETED.value, "Task completed by user.", 23, 0)
            if offset % 4 in {1, 2}:
                add_history(db, cook, day, HistoryAction.COMPLETED.value, "Task completed by user.", 20, 10)
            else:
                add_history(
                    db,
                    cook,
                    day,
                    HistoryAction.DEFERRED.value,
                    f"Task deferred to {(day + timedelta(days=1)).isoformat()} by user.",
                    17,
                    30,
                )

        for weeks_back in range(7, 0, -1):
            tue = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks_back) + timedelta(days=1)
            thu = tue + timedelta(days=2)
            fri = tue + timedelta(days=3)
            sun = tue + timedelta(days=5)
            add_history(db, cafe, tue, HistoryAction.COMPLETED.value, "Weekly shift completed.", 22, 0)
            add_history(db, critique, thu, HistoryAction.COMPLETED.value, "Critique attended and notes captured.", 17, 50)
            add_history(db, parents, fri, HistoryAction.COMPLETED.value, "Family check-in completed.", 20, 30)
            if weeks_back == 2:
                add_history(
                    db,
                    reset,
                    sun,
                    HistoryAction.DEFERRED.value,
                    f"Task deferred to {(sun + timedelta(days=1)).isoformat()} by user.",
                    18,
                    10,
                )
            else:
                add_history(db, reset, sun, HistoryAction.COMPLETED.value, "Weekly reset completed.", 19, 15)

        add_history(
            db,
            capstone,
            today - timedelta(days=8),
            HistoryAction.PLANNED.value,
            "Pulled into the weekly plan before critique prep.",
            8,
            10,
        )
        add_history(
            db,
            capstone,
            today - timedelta(days=4),
            HistoryAction.DEFERRED.value,
            f"Task deferred to {(today + timedelta(days=3)).isoformat()} by user.",
            18,
            20,
        )
        add_history(
            db,
            follow_up,
            today - timedelta(days=2),
            HistoryAction.DEFERRED.value,
            f"Task deferred to {(today + timedelta(days=4)).isoformat()} by user.",
            16,
            25,
        )
        add_history(
            db,
            birthday,
            today - timedelta(days=1),
            HistoryAction.PLANNED.value,
            "Held for next week's relationship prep.",
            9,
            15,
        )
        add_history(
            db,
            license_task,
            today - timedelta(days=6),
            HistoryAction.DEFERRED.value,
            f"Task deferred to {(today + timedelta(days=14)).isoformat()} by user.",
            15,
            50,
        )
        add_history(db, reflection, today - timedelta(days=10), HistoryAction.COMPLETED.value, "Task completed by user.", 18, 15)
        add_history(db, tickets, today - timedelta(days=7), HistoryAction.COMPLETED.value, "Task completed by user.", 14, 30)
        add_history(db, portfolio, today - timedelta(days=5), HistoryAction.COMPLETED.value, "Task completed by user.", 21, 0)
        add_history(db, club, today - timedelta(days=19), HistoryAction.DELETED.value, "Task deleted by user.", 12, 0)
        add_history(db, gym, today - timedelta(days=21), HistoryAction.DELETED.value, "Task deleted by user.", 13, 15)

        # Review calendar and plan trail.
        recent_plan_map = {
            today - timedelta(days=6): [
                (water, PlanTaskStatus.COMPLETED.value, "Easy win habit."),
                (cafe, PlanTaskStatus.COMPLETED.value, "Protected shift block."),
                (follow_up, PlanTaskStatus.PLANNED.value, "Left for later in the week."),
            ],
            today - timedelta(days=5): [
                (walk, PlanTaskStatus.COMPLETED.value, "Recovery after classes."),
                (parents, PlanTaskStatus.COMPLETED.value, "Weekly family call."),
                (portfolio, PlanTaskStatus.COMPLETED.value, "Quick polish session."),
            ],
            today - timedelta(days=4): [
                (water, PlanTaskStatus.COMPLETED.value, "Stayed consistent."),
                (critique, PlanTaskStatus.COMPLETED.value, "Important school block."),
                (capstone, PlanTaskStatus.DEFERRED.value, "Needed one more pass after critique."),
            ],
            today - timedelta(days=3): [
                (cook, PlanTaskStatus.COMPLETED.value, "Low-spend dinner night."),
                (walk, PlanTaskStatus.DEFERRED.value, "Rainy evening, moved forward."),
                (journal, PlanTaskStatus.COMPLETED.value, "Short reflection before sleep."),
            ],
            today - timedelta(days=2): [
                (water, PlanTaskStatus.COMPLETED.value, "Routine stayed on track."),
                (follow_up, PlanTaskStatus.DEFERRED.value, "Wanted a stronger draft first."),
                (birthday, PlanTaskStatus.PLANNED.value, "Still upcoming."),
            ],
            today - timedelta(days=1): [
                (cook, PlanTaskStatus.DEFERRED.value, "Grabbed dinner out with friends."),
                (journal, PlanTaskStatus.COMPLETED.value, "Weekend reflection."),
                (birthday, PlanTaskStatus.PLANNED.value, "Need to book next week."),
            ],
            today: [
                (water, PlanTaskStatus.PLANNED.value, "Still open today."),
                (capstone, PlanTaskStatus.PLANNED.value, "Main push for the next few days."),
                (walk, PlanTaskStatus.PLANNED.value, "Kept as a low-stress reset."),
            ],
            today + timedelta(days=1): [
                (reset, PlanTaskStatus.PLANNED.value, "Sunday reset block."),
                (license_task, PlanTaskStatus.PLANNED.value, "Admin task with plenty of runway."),
                (birthday, PlanTaskStatus.PLANNED.value, "Reservation research."),
            ],
            today + timedelta(days=3): [
                (capstone, PlanTaskStatus.PLANNED.value, "Slide deadline."),
                (cafe, PlanTaskStatus.PLANNED.value, "Shift still protected."),
                (follow_up, PlanTaskStatus.PLANNED.value, "Send right after slides."),
            ],
        }
        for plan_day, picks in recent_plan_map.items():
            create_plan(db, user.id, plan_day, picks)

        # Mood trail with multiple check-ins on the same day so the account feels
        # genuinely lived in instead of looking like a once-a-day demo.
        mood_days = {
            30: [
                (2, "Woke up already behind and a little foggy.", 9, 5),
                (3, "A walk after lunch helped me reset.", 14, 20),
                (4, "Ended the day steadier than it started.", 22, 10),
            ],
            27: [
                (3, "Slow morning, but not bad.", 8, 40),
                (4, "Studio feedback felt sharp instead of discouraging.", 16, 45),
            ],
            24: [
                (2, "Low energy and stayed inside too long.", 11, 30),
                (3, "Cooking helped a bit tonight.", 20, 55),
            ],
            22: [
                (3, "Inbox looked messy at first.", 10, 10),
                (4, "Felt steady after finally clearing inbox tasks.", 18, 5),
            ],
            19: [
                (4, "Had decent momentum in the morning.", 9, 0),
                (5, "Capstone work clicked today.", 15, 35),
                (4, "Tired now, but in a good way.", 23, 0),
            ],
            16: [
                (3, "Busy Tuesday shift, not much room for anything else.", 21, 40),
            ],
            14: [
                (3, "Started neutral.", 9, 15),
                (4, "Small wins made the week feel lighter.", 19, 10),
            ],
            12: [
                (2, "Too much context-switching.", 13, 5),
                (3, "A little better after stepping away from the screen.", 17, 40),
            ],
            10: [
                (4, "Good energy from the start.", 10, 0),
                (5, "Portfolio fix was quick and satisfying.", 21, 0),
            ],
            8: [
                (3, "Still waking up slowly.", 8, 20),
                (4, "Better sleep made a huge difference.", 12, 50),
                (4, "Trying not to overfill tomorrow.", 22, 35),
            ],
            6: [
                (4, "Had momentum in the morning.", 10, 40),
                (3, "Then slowed down once messages piled up.", 18, 15),
            ],
            4: [
                (3, "A little tense before critique.", 11, 10),
                (4, "Critique was intense but useful.", 17, 55),
            ],
            2: [
                (3, "Still slightly overloaded.", 12, 5),
                (2, "Energy dipped hard in the afternoon.", 16, 35),
                (3, "Recovered enough to prep tomorrow.", 22, 25),
            ],
            1: [
                (4, "Feeling more organized than earlier this month.", 21, 45),
            ],
            0: [
                (3, "Started a bit mentally noisy.", 9, 20),
                (4, "Things felt more under control after lunch.", 14, 45),
                (4, "Need a calm finish to the week, but overall things feel under control.", 22, 15),
            ],
        }
        for offset, entries in mood_days.items():
            add_mood_entries(db, user.id, today - timedelta(days=offset), entries)

        # Focus trail
        focus_blocks = [
            (11, capstone, 50),
            (10, capstone, 40),
            (9, portfolio, 30),
            (8, capstone, 55),
            (7, follow_up, 25),
            (6, capstone, 45),
            (5, capstone, 50),
            (4, critique, 35),
            (3, capstone, 60),
            (2, birthday, 20),
            (1, follow_up, 30),
            (0, capstone, 45),
        ]
        for index, (offset, task, minutes) in enumerate(focus_blocks):
            day = today - timedelta(days=offset)
            db.add(
                FocusSession(
                    user_id=user.id,
                    task_id=task.id,
                    date=day.isoformat(),
                    duration_minutes=minutes,
                    session_type="work",
                    created_at=stamp(day, 14 + (index % 3), 10),
                )
            )

        # Daily fortunes cached in English.
        for offset in range(9, -1, -1):
            day = today - timedelta(days=offset)
            db.add(
                DailyFortune(
                    user_id=user.id,
                    date=day.isoformat(),
                    fortune_data=json.dumps(
                        {
                            "lang": "en",
                            "headline": "Keep the day smaller than your ambition.",
                            "energy": "steady" if offset % 2 == 0 else "reflective",
                            "focus": "school" if offset % 3 == 0 else "maintenance",
                            "note": "The best next move is still the smallest one you will actually finish.",
                        },
                        ensure_ascii=False,
                    ),
                    created_at=stamp(day, 7, 5),
                )
            )

        onboarding = {
            "completed": True,
            "daily_capacity": 5,
            "profile_summary": "chen has been using Daymark to balance classes, a cafe shift, health habits, and relationship reminders.",
            "brain_dump": "Follow up on internships\nKeep room clean\nDon't forget admin tasks",
            "commitments": "Drink 2L of water\nTake a 20-minute walk\nCook dinner at home\nTuesday cafe shift\nThursday design critique",
            "goals": "Finish capstone slides\nSend internship follow-up\nBook birthday dinner for Maya",
        }
        upsert_json_setting(db, onboarding_key(user.id), onboarding)

        assistant_profile = dict(DEFAULT_PROFILE)
        assistant_profile.update(
            {
                "completed": True,
                "next_question_index": 5,
                "summary": "English-speaking student using the app to manage school, part-time work, habits, and a few personal commitments.",
                "answers": {
                    "main_focus": "Capstone work, internship follow-up, and staying consistent with routines.",
                    "protected_commitments": "Tuesday cafe shift, Thursday critique, and Friday family calls.",
                    "planning_pain": "Overcommitting when school gets busy.",
                    "energy_pattern": "Sharper in the late morning and calmer at night.",
                    "assistant_style": "Direct, but not cold.",
                },
            }
        )
        upsert_json_setting(db, f"assistant_profile:{user.id}", assistant_profile)

        history = dict(DEFAULT_HISTORY)
        history["messages"] = [
            {
                "id": "assistant-1",
                "role": "assistant",
                "content": "I'm your private concierge inside this app. You can ask normal questions or tell me to change tasks.",
                "created_at": stamp(today - timedelta(days=2), 9, 0).isoformat(),
            },
            {
                "id": "user-1",
                "role": "user",
                "content": "What is still on my plate for next week?",
                "created_at": stamp(today - timedelta(days=2), 9, 1).isoformat(),
            },
            {
                "id": "assistant-2",
                "role": "assistant",
                "content": "Next week is mainly capstone slides, your internship follow-up, Maya's birthday dinner, and your regular Tuesday shift.",
                "created_at": stamp(today - timedelta(days=2), 9, 1).isoformat(),
            },
            {
                "id": "user-2",
                "role": "user",
                "content": "Move the DMV task later.",
                "created_at": stamp(today - timedelta(days=1), 18, 10).isoformat(),
            },
            {
                "id": "assistant-3",
                "role": "assistant",
                "content": "Done. I pushed Renew driver's license further out so it stops competing with capstone week.",
                "created_at": stamp(today - timedelta(days=1), 18, 11).isoformat(),
            },
        ]
        upsert_json_setting(db, f"assistant_history:{user.id}", history)
        upsert_json_setting(db, f"assistant_pending:{user.id}", dict(DEFAULT_PENDING))

        print(f"Seeded protected showcase user '{SHOWCASE_USERNAME}' with rich English demo data.")
        print("Login credentials:")
        print(f"  username: {SHOWCASE_USERNAME}")
        print(f"  password: {SHOWCASE_PASSWORD}")


if __name__ == "__main__":
    main()
