"""对外可传输的 Agent 事件信封和稳定事件类型。"""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class EventType(StrEnum):
    RUN_STARTED = "run.started"
    PLAN_UPDATED = "plan.updated"
    MODEL_DELTA = "model.delta"
    TOOL_PROPOSED = "tool.proposed"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"
    APPROVAL_REQUIRED = "approval.required"
    APPROVAL_RESOLVED = "approval.resolved"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_INTERRUPTED = "run.interrupted"
    RUN_CANCELLED = "run.cancelled"
    HEARTBEAT = "heartbeat"


class AgentEvent(BaseModel):
    """版本化事件契约；拒绝额外字段和非标准 JSON 浮点值以保证跨系统回放。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    schema_version: Literal[1] = 1
    run_id: UUID
    sequence: int = Field(ge=1)
    type: EventType
    created_at: datetime
    data: dict[str, JsonValue]
