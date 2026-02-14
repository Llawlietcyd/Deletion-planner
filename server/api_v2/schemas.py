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


class PlanGenerateRequest(BaseModel):
    date: Optional[str] = None
    lang: str = "en"


class FeedbackEntry(BaseModel):
    plan_task_id: int
    status: PlanTaskStatus


class FeedbackSubmitRequest(BaseModel):
    date: Optional[str] = None
    results: List[FeedbackEntry]
    lang: str = "en"
