from datetime import date, datetime

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    priority: str = Field("medium", pattern="^(high|medium|low)$")
    status: str = Field("todo", pattern="^(todo|in_progress|done)$")
    due_date: date | None = None
    tag: str | None = Field(None, max_length=50)
    task_type: str = Field("short_term", pattern="^(short_term|long_term|daily)$")
    deadline_precision: str | None = Field(None, pattern="^(day|month|year)$")
    timer_preset: int | None = Field(None, ge=60, le=7200)
    parent_id: int | None = None


class TaskUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    priority: str = Field(..., pattern="^(high|medium|low)$")
    status: str = Field(..., pattern="^(todo|in_progress|done)$")
    due_date: date | None = None
    tag: str | None = Field(None, max_length=50)
    task_type: str = Field(..., pattern="^(short_term|long_term|daily)$")
    deadline_precision: str | None = Field(None, pattern="^(day|month|year)$")
    timer_preset: int | None = Field(None, ge=60, le=7200)


class TimerUpdate(BaseModel):
    """每日任务计时上报"""
    total_seconds: int = Field(..., ge=0, description="累计秒数")


class TaskResponse(BaseModel):
    id: int
    parent_id: int | None
    owner_id: int
    title: str
    description: str | None
    priority: str
    status: str
    due_date: date | None
    tag: str | None
    task_type: str
    deadline_precision: str | None
    timer_preset: int | None
    timer_total_seconds: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
