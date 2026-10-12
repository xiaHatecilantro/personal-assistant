"""Agent 运行审计表。

这些 MySQL 表保存可查询的业务事实、事件、审批和工具执行结果；LangGraph 的完整运行
快照由 PostgreSQL Checkpointer 管理。两类存储用途不同，不能相互替代。
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.agent.schemas import RunStatus
from app.config import Base


class AgentRun(Base):
    """一次 Agent 运行的业务主记录，也是事件和工具操作的并发归属边界。"""

    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_owner_status", "owner_id", "status"),
        Index("ix_agent_runs_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=RunStatus.QUEUED.value)
    thread_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    graph_version: Mapped[str] = mapped_column(String(50), nullable=False)
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    final_answer: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AgentEvent(Base):
    """按 run_id 和 sequence 唯一排序的追加式事件，用于回放和前端增量消费。"""

    __tablename__ = "agent_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_agent_events_run_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AgentApproval(Base):
    """高风险工具调用的人工审批记录；tool_call_id 在单次运行内必须唯一。"""

    __tablename__ = "agent_approvals"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "tool_call_id",
            name="uq_agent_approvals_run_tool_call",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    tool_call_id: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(50), nullable=False)
    arguments_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    arguments_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    decision: Mapped[str | None] = mapped_column(String(32))
    decision_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AgentToolExecution(Base):
    """工具执行审计与幂等结果；重复 tool_call_id 不能产生第二次副作用。"""

    __tablename__ = "agent_tool_executions"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "tool_call_id",
            name="uq_agent_tool_executions_run_tool_call",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    tool_call_id: Mapped[str] = mapped_column(String(128), nullable=False)
    arguments_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="running")
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    business_entity_type: Mapped[str | None] = mapped_column(String(100))
    business_entity_id: Mapped[str | None] = mapped_column(String(100))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
