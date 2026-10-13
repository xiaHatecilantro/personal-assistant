"""Agent HTTP/服务层契约：运行状态、展示模型与人工审批输入。"""

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator


class RunStatus(StrEnum):
    """持久化运行状态；合法状态迁移由 ``agent.policies`` 单独约束。"""

    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLING = "cancelling"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"


class ApprovalDecisionType(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


class AgentContract(BaseModel):
    """Agent 契约基类：支持 ORM 映射并拒绝未知字段和非标准 JSON 浮点值。"""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        allow_inf_nan=False,
    )


class RunCreate(AgentContract):
    goal: str = Field(min_length=1, max_length=4000)

    @field_validator("goal")
    @classmethod
    def normalize_goal(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("goal must not be blank")
        return value


class RunSummary(AgentContract):
    id: UUID
    goal: str
    status: RunStatus
    created_at: datetime
    updated_at: datetime


class RunDetail(RunSummary):
    thread_id: UUID
    graph_version: str
    max_steps: int = Field(gt=0)
    timeout_seconds: int = Field(gt=0)
    step_count: int = Field(ge=0)
    final_answer: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None


class ApprovalDecision(AgentContract):
    """审批决定；仅 edit 必须携带修改后的工具参数。"""

    decision: ApprovalDecisionType
    revision: int = Field(ge=1)
    edited_arguments: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def validate_edited_arguments(self) -> Self:
        has_edited_arguments = self.edited_arguments is not None
        if self.decision is ApprovalDecisionType.EDIT and not has_edited_arguments:
            raise ValueError("edit decision requires edited_arguments")
        if self.decision is not ApprovalDecisionType.EDIT and has_edited_arguments:
            raise ValueError("edited_arguments are only valid for edit decisions")
        return self
