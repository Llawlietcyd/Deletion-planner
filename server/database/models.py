from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, ForeignKey, Enum, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime, timezone
import enum
import os

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

# ---------- Models ----------

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    category = Column(String(30), default=TaskCategory.UNCLASSIFIED.value)
    status = Column(String(20), default=TaskStatus.ACTIVE.value)
    priority = Column(Integer, default=0)  # higher = more important
    deferral_count = Column(Integer, default=0)
    completion_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    plan_tasks = relationship("PlanTask", back_populates="task", cascade="all, delete-orphan")
    history = relationship("TaskHistory", back_populates="task", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "status": self.status,
            "priority": self.priority,
            "deferral_count": self.deferral_count,
            "completion_count": self.completion_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DailyPlan(Base):
    __tablename__ = "daily_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False, unique=True)  # YYYY-MM-DD
    reasoning = Column(Text, default="")
    overload_warning = Column(Text, default="")
    max_tasks = Column(Integer, default=4)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    plan_tasks = relationship("PlanTask", back_populates="plan", cascade="all, delete-orphan")

    def to_dict(self, include_tasks=False):
        result = {
            "id": self.id,
            "date": self.date,
            "reasoning": self.reasoning,
            "overload_warning": self.overload_warning,
            "max_tasks": self.max_tasks,
            "created_at": self.created_at.isoformat() if self.created_at else None,
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
            "date": self.date,
            "action": self.action,
            "ai_reasoning": self.ai_reasoning,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
