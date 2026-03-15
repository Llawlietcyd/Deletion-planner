from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone
import enum
import os
from core.time import datetime_to_iso, normalize_date_string

Base = declarative_base()

# ---------- Enums ----------

class TaskCategory(str, enum.Enum):
    CORE = "core"
    DEFERRABLE = "deferrable"
    DELETION_CANDIDATE = "deletion_candidate"
    UNCLASSIFIED = "unclassified"

class TaskStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DELETED = "deleted"

class PlanTaskStatus(str, enum.Enum):
    PLANNED = "planned"
    COMPLETED = "completed"
    MISSED = "missed"
    DEFERRED = "deferred"

class HistoryAction(str, enum.Enum):
    CREATED = "created"
    PLANNED = "planned"
    COMPLETED = "completed"
    MISSED = "missed"
    DEFERRED = "deferred"
    DELETED = "deleted"
    RESTORED = "restored"

# ---------- Models ----------

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_username", "username"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), nullable=False, unique=True)
    password = Column(String(128), nullable=False)
    birthday = Column(String(10), nullable=True)   # YYYY-MM-DD
    gender = Column(String(20), nullable=True)      # male/female/other/prefer_not_to_say
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("idx_user_sessions_token", "token"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(128), nullable=False, unique=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="sessions")

class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_created_at", "created_at"),
        Index("idx_tasks_sort_order", "sort_order"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, default=1)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    category = Column(String(30), default=TaskCategory.UNCLASSIFIED.value)
    status = Column(String(20), default=TaskStatus.ACTIVE.value)
    priority = Column(Integer, default=0)  # higher = more important
    sort_order = Column(Integer, default=0)  # lower value appears first
    deferral_count = Column(Integer, default=0)
    completion_count = Column(Integer, default=0)
    source = Column(String(20), default="manual")  # manual / ai / rule
    task_kind = Column(String(20), default="temporary")  # daily / weekly / temporary
    recurrence_weekday = Column(Integer, nullable=True)  # 0=Mon .. 6=Sun for weekly tasks
    decision_reason = Column(Text, default="")
    completed_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    due_date = Column(String(10), nullable=True)  # YYYY-MM-DD
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="tasks")
    plan_tasks = relationship("PlanTask", back_populates="task", cascade="all, delete-orphan")
    history = relationship("TaskHistory", back_populates="task", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "status": self.status,
            "priority": self.priority,
            "sort_order": self.sort_order,
            "deferral_count": self.deferral_count,
            "completion_count": self.completion_count,
            "source": self.source,
            "task_kind": self.task_kind or "temporary",
            "recurrence_weekday": self.recurrence_weekday,
            "decision_reason": self.decision_reason,
            "completed_at": datetime_to_iso(self.completed_at),
            "deleted_at": datetime_to_iso(self.deleted_at),
            "due_date": normalize_date_string(self.due_date),
            "created_at": datetime_to_iso(self.created_at),
            "updated_at": datetime_to_iso(self.updated_at),
        }


class DailyPlan(Base):
    __tablename__ = "daily_plans"
    __table_args__ = (
        Index("idx_daily_plans_date", "date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(32), nullable=False, unique=True)  # "{user_id}:{YYYY-MM-DD}"
    reasoning = Column(Text, default="")
    overload_warning = Column(Text, default="")
    max_tasks = Column(Integer, default=4)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    plan_tasks = relationship("PlanTask", back_populates="plan", cascade="all, delete-orphan")

    def to_dict(self, include_tasks=False):
        display_date = self.date
        if isinstance(display_date, str) and ":" in display_date:
            maybe_prefix, maybe_date = display_date.split(":", 1)
            if maybe_prefix.isdigit():
                display_date = maybe_date
        result = {
            "id": self.id,
            "date": display_date,
            "reasoning": self.reasoning,
            "overload_warning": self.overload_warning,
            "max_tasks": self.max_tasks,
            "created_at": datetime_to_iso(self.created_at),
        }
        if include_tasks:
            result["tasks"] = [pt.to_dict() for pt in self.plan_tasks]
        return result


class PlanTask(Base):
    __tablename__ = "plan_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey("daily_plans.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    status = Column(String(20), default=PlanTaskStatus.PLANNED.value)
    order = Column(Integer, default=0)

    # Relationships
    plan = relationship("DailyPlan", back_populates="plan_tasks")
    task = relationship("Task", back_populates="plan_tasks")

    def to_dict(self):
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "status": self.status,
            "order": self.order,
            "task": self.task.to_dict() if self.task else None,
        }


class TaskHistory(Base):
    __tablename__ = "task_history"
    __table_args__ = (
        Index("idx_task_history_date", "date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    action = Column(String(20), nullable=False)
    ai_reasoning = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    task = relationship("Task", back_populates="history")

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "task_title": self.task.title if self.task else None,
            "date": self.date,
            "action": self.action,
            "ai_reasoning": self.ai_reasoning,
            "created_at": datetime_to_iso(self.created_at),
        }


class AppSetting(Base):
    """Key-value store for application settings (e.g. LLM config)."""
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, default="")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class MoodEntry(Base):
    __tablename__ = "mood_entries"
    __table_args__ = (
        Index("idx_mood_entries_user_date", "user_id", "date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    mood_level = Column(Integer, nullable=False)  # 1-5 (terrible to great)
    note = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DailyFortune(Base):
    __tablename__ = "daily_fortunes"
    __table_args__ = (
        Index("idx_daily_fortunes_user_date", "user_id", "date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(String(10), nullable=False)
    fortune_data = Column(Text, default="{}")  # JSON string
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class FocusSession(Base):
    __tablename__ = "focus_sessions"
    __table_args__ = (
        Index("idx_focus_sessions_user_date", "user_id", "date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    date = Column(String(10), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    session_type = Column(String(10), default="work")  # work/break
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
