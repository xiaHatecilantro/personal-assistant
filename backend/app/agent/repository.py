"""Agent 运行审计仓储：封装事务内写入、状态 CAS、行锁和幂等约束。"""

from datetime import datetime, timezone
from typing import Any

from pydantic import ConfigDict, JsonValue, TypeAdapter
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.agent.policies import ensure_run_transition
from app.agent.schemas import RunStatus
from app.agent_models import AgentApproval, AgentEvent, AgentRun, AgentToolExecution


class IdempotencyConflict(RuntimeError):
    pass


_JSON_OBJECT_ADAPTER = TypeAdapter(
    dict[str, JsonValue],
    config=ConfigDict(strict=True, allow_inf_nan=False),
)
# 数据库 JSON 类型可能接受 NaN/Infinity 等非标准值，因此必须在写库前统一收紧。


def _validate_json_object(value: dict[str, Any]) -> dict[str, JsonValue]:
    return _JSON_OBJECT_ADAPTER.validate_python(value)


def _lock_run(session: Session, run_id: str) -> None:
    """锁定父运行行，使同一 run 下的序号分配和幂等检查串行执行。"""
    session.execute(
        select(AgentRun.id).where(AgentRun.id == run_id).with_for_update()
    ).scalar_one()


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_run(
    session: Session,
    *,
    run_id: str,
    owner_id: int,
    goal: str,
    graph_version: str,
    max_steps: int,
    timeout_seconds: int,
) -> AgentRun:
    """创建运行但不提交事务，提交/回滚边界由上层用例统一决定。"""
    run = AgentRun(
        id=run_id,
        owner_id=owner_id,
        goal=goal,
        # 业务主键同时作为 Checkpoint thread，避免恢复时混用两套身份。
        thread_id=run_id,
        graph_version=graph_version,
        max_steps=max_steps,
        timeout_seconds=timeout_seconds,
    )
    session.add(run)
    session.flush()
    return run


def get_run_for_owner(session: Session, run_id: str, owner_id: int) -> AgentRun | None:
    """按 owner_id 限定查询，防止仅凭可猜测的 run_id 跨用户读取。"""
    return session.scalar(
        select(AgentRun).where(AgentRun.id == run_id, AgentRun.owner_id == owner_id)
    )


def compare_and_set_status(
    session: Session,
    *,
    run_id: str,
    owner_id: int,
    expected_status: RunStatus,
    new_status: RunStatus,
) -> bool:
    """使用状态和 owner 作为 CAS 条件，避免并发请求覆盖已经变化的运行状态。"""
    ensure_run_transition(expected_status, new_status)
    result = session.execute(
        update(AgentRun)
        .where(
            AgentRun.id == run_id,
            AgentRun.owner_id == owner_id,
            AgentRun.status == expected_status.value,
        )
        .values(status=new_status.value)
    )
    return result.rowcount == 1


def append_event(
    session: Session,
    *,
    run_id: str,
    event_type: str,
    payload_json: dict[str, Any],
) -> AgentEvent:
    """统一脱敏公开事件，再于父行锁下分配单调序号。"""
    # event_recorder 依赖 append_event；在调用边界延迟导入以避免模块循环初始化。
    from app.agent.event_recorder import redact_public_value

    payload_json = _validate_json_object(payload_json)
    payload_json = redact_public_value(payload_json)
    _lock_run(session, run_id)
    latest_sequence = session.scalar(
        select(AgentEvent.sequence)
        .where(AgentEvent.run_id == run_id)
        .order_by(AgentEvent.sequence.desc())
        .limit(1)
        .with_for_update()
    )
    event = AgentEvent(
        run_id=run_id,
        sequence=(latest_sequence or 0) + 1,
        event_type=event_type,
        payload_json=payload_json,
    )
    session.add(event)
    session.flush()
    return event


def create_approval(
    session: Session,
    *,
    run_id: str,
    tool_call_id: str,
    tool_name: str,
    tool_version: str,
    arguments_json: dict[str, Any],
    arguments_hash: str,
) -> AgentApproval:
    """幂等创建审批；相同调用 ID 只有所有不可变输入一致时才允许复用。"""
    arguments_json = _validate_json_object(arguments_json)
    _lock_run(session, run_id)
    existing = session.scalar(
        select(AgentApproval).where(
            AgentApproval.run_id == run_id,
            AgentApproval.tool_call_id == tool_call_id,
        ).with_for_update()
    )
    if existing is not None:
        if (
            existing.arguments_hash != arguments_hash
            or existing.tool_name != tool_name
            or existing.tool_version != tool_version
            or existing.arguments_json != arguments_json
        ):
            raise IdempotencyConflict(
                f"tool call {tool_call_id!r} was already recorded with different data"
            )
        return existing

    approval = AgentApproval(
        run_id=run_id,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        tool_version=tool_version,
        arguments_json=arguments_json,
        arguments_hash=arguments_hash,
    )
    session.add(approval)
    session.flush()
    return approval


def record_tool_execution(
    session: Session,
    *,
    run_id: str,
    tool_call_id: str,
    arguments_hash: str,
    status: str,
    result_json: dict[str, Any] | None,
    business_entity_type: str | None,
    business_entity_id: str | None,
    duration_ms: int | None,
) -> AgentToolExecution:
    """记录一次终态工具结果，相同参数哈希的重复请求直接复用首次结果。"""
    if status not in {"completed", "failed"}:
        raise ValueError("tool execution status must be 'completed' or 'failed'")
    if result_json is not None:
        result_json = _validate_json_object(result_json)
    _lock_run(session, run_id)
    existing = session.scalar(
        select(AgentToolExecution).where(
            AgentToolExecution.run_id == run_id,
            AgentToolExecution.tool_call_id == tool_call_id,
        ).with_for_update()
    )
    if existing is not None:
        if existing.arguments_hash != arguments_hash:
            raise IdempotencyConflict(
                f"tool call {tool_call_id!r} was already executed with different arguments"
            )
        return existing

    execution = AgentToolExecution(
        run_id=run_id,
        tool_call_id=tool_call_id,
        arguments_hash=arguments_hash,
        status=status,
        result_json=result_json,
        business_entity_type=business_entity_type,
        business_entity_id=business_entity_id,
        duration_ms=duration_ms,
        finished_at=_utcnow_naive(),
    )
    session.add(execution)
    session.flush()
    return execution
