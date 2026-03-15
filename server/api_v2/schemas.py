from typing import List, Optional, Literal
from pydantic import BaseModel, Field


TaskCategory = Literal["core", "deferrable", "deletion_candidate", "unclassified"]
TaskStatus = Literal["active", "completed", "deleted"]
PlanTaskStatus = Literal["planned", "completed", "missed", "deferred"]


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Optional[dict] = None


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    priority: int = 0
    sort_order: int = 0
    category: TaskCategory = "unclassified"
    due_date: Optional[str] = None
    task_kind: Optional[str] = None
    recurrence_weekday: Optional[int] = None


class TaskBatchCreateRequest(BaseModel):
    text: str


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    priority: Optional[int] = None
    sort_order: Optional[int] = None
    category: Optional[TaskCategory] = None
    status: Optional[TaskStatus] = None
    deferral_count_delta: Optional[int] = None
    due_date: Optional[str] = None
    task_kind: Optional[str] = None
    recurrence_weekday: Optional[int] = None


class PlanGenerateRequest(BaseModel):
    date: Optional[str] = None
    lang: str = "en"
    capacity_units: Optional[int] = Field(default=None, ge=1, le=24)
    force: bool = False


class FeedbackEntry(BaseModel):
    plan_task_id: int
    status: PlanTaskStatus


class FeedbackSubmitRequest(BaseModel):
    date: Optional[str] = None
    results: List[FeedbackEntry]
    lang: str = "en"
    capacity_units: Optional[int] = Field(default=None, ge=1, le=24)


class ReorderRequest(BaseModel):
    ordered_task_ids: List[int] = Field(min_length=1)


class SessionLoginRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=4, max_length=128)
    birthday: Optional[str] = None   # YYYY-MM-DD
    gender: Optional[str] = None     # male/female/other/prefer_not_to_say


class OnboardingCompleteRequest(BaseModel):
    brain_dump: str = ""
    commitments: str = ""
    goals: str = ""
    daily_capacity: int = Field(default=6, ge=1, le=24)
    lang: str = "en"
    reset_existing: bool = True


class MoodCreateRequest(BaseModel):
    mood_level: int = Field(ge=1, le=5)
    note: str = ""


class FocusSessionCreateRequest(BaseModel):
    task_id: Optional[int] = None
    duration_minutes: int = Field(ge=1, le=120)
    session_type: str = "work"


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    lang: str = "en"
