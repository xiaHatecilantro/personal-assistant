"""Agent Run 的异步启动、只读查询和可恢复事件流接口。"""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.agent.events import AgentEvent as EventEnvelope
from app.agent.events import EventType
from app.agent.policies import ensure_run_transition, hash_arguments
from app.agent.repository import append_event, create_run, get_run_for_owner
from app.agent.runtime import (
    DEFAULT_GRAPH_VERSION, DuplicateRunError, RunNotStartableError,
    RuntimePreparationError, RuntimeShuttingDownError,
)
from app.agent.schemas import ApprovalDecision, ApprovalDecisionType, RunCreate, RunDetail, RunStatus, RunSummary
from app.agent.tools.notes import CreateNoteInput
from app.agent.tools.tasks import CreateTaskInput, UpdateTaskInput
from app.agent_models import AgentApproval
from app.agent_models import AgentEvent as EventRecord
from app.agent_models import AgentRun
from app.auth import get_current_user
from app.config import SessionLocal, get_db
from app.models import User
from app.settings import get_settings


class AgentRuntimePort(Protocol):
    def start(self, run_id: str) -> object: ...

    def resume(self, run_id: str) -> object: ...

    def request_cancel(self, run_id: str) -> None: ...

    def resume_interrupted(self, run_id: str) -> object: ...


router = APIRouter(prefix="/api/v1/agent", tags=["agent"])
TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}
AgentSessionFactory = Callable[[], Session]


def _validated_approval_arguments(tool_name: str, arguments: dict) -> dict:
    """审批编辑与实际执行使用同一工具输入模型，避免参数漂移。"""
    models = {
        "create_task": CreateTaskInput,
        "update_task": UpdateTaskInput,
        "create_note": CreateNoteInput,
    }
    model = models.get(tool_name)
    if model is None:
        raise HTTPException(status_code=422, detail="不支持编辑此工具的参数")
    try:
        validated = model.model_validate(arguments)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="工具参数校验失败") from exc
    return validated.model_dump(mode="json", exclude_unset=True)


def get_agent_runtime(request: Request) -> AgentRuntimePort:
    """从应用生命周期取得 Runtime，避免在请求内创建 Checkpointer 连接。"""
    runtime = getattr(request.app.state, "agent_runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="Agent Runtime 尚未就绪")
    return runtime


def get_agent_session_factory() -> AgentSessionFactory:
    """SSE 每次轮询创建短 Session，不能持有已经结束的请求 Session。"""
    return SessionLocal


@router.post("/runs", response_model=RunDetail, status_code=status.HTTP_202_ACCEPTED)
async def create_agent_run(
    body: RunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    runtime: AgentRuntimePort = Depends(get_agent_runtime),
):
    """先提交业务记录，再启动只持有 run_id 的后台任务。"""
    settings = get_settings()
    run_id = str(uuid4())
    run = create_run(
        db,
        run_id=run_id,
        owner_id=current_user.id,
        goal=body.goal,
        graph_version=DEFAULT_GRAPH_VERSION,
        max_steps=settings.agent_max_steps,
        timeout_seconds=settings.agent_run_timeout_seconds,
    )
    db.commit()
    db.refresh(run)

    # Runtime 会用全新的 Session 重新读取该记录，不跨请求共享 ORM 对象。
    runtime.start(run.id)
    return run


@router.get("/runs", response_model=list[RunSummary])
def list_agent_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(AgentRun)
        .where(AgentRun.owner_id == current_user.id)
        .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
    ).all()


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_agent_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = get_run_for_owner(db, run_id, current_user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent Run 不存在")
    return run


@router.post("/runs/{run_id}/cancel", response_model=RunDetail)
def cancel_agent_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    runtime: AgentRuntimePort = Depends(get_agent_runtime),
):
    """先持久化取消意图，再通知进程内任务；终态重复请求保持原结果。"""
    run = db.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id, AgentRun.owner_id == current_user.id
        ).with_for_update()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Agent Run 不存在")
    if run.status in TERMINAL_RUN_STATUSES:
        return run
    if run.status == RunStatus.INTERRUPTED.value:
        # 中断线程没有活跃 task；直接转为终态，不能为了取消而重放 Checkpoint。
        ensure_run_transition(RunStatus.INTERRUPTED, RunStatus.CANCELLED)
        run.status = RunStatus.CANCELLED.value
        run.cancel_requested_at = datetime.now(timezone.utc).replace(tzinfo=None)
        run.finished_at = run.cancel_requested_at
        append_event(db, run_id=run_id, event_type="run.cancelled", payload_json={})
        db.commit()
        db.refresh(run)
        return run
    if run.status not in (
        RunStatus.RUNNING.value,
        RunStatus.WAITING_APPROVAL.value,
        RunStatus.CANCELLING.value,
    ):
        raise HTTPException(status_code=409, detail="Run 当前不可取消")
    if run.status != RunStatus.CANCELLING.value:
        ensure_run_transition(RunStatus(run.status), RunStatus.CANCELLING)
        run.status = RunStatus.CANCELLING.value
        run.cancel_requested_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    runtime.request_cancel(run_id)
    db.refresh(run)
    return run


@router.post("/runs/{run_id}/resume", response_model=RunDetail)
async def resume_interrupted_agent_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    runtime: AgentRuntimePort = Depends(get_agent_runtime),
):
    """先查 owner，再按原线程显式恢复；不暴露其他用户 Run 的存在性。"""
    run = get_run_for_owner(db, run_id, current_user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent Run 不存在")
    if run.status != RunStatus.INTERRUPTED.value or run.cancel_requested_at is not None:
        raise HTTPException(status_code=409, detail="Run 当前不可恢复")
    try:
        runtime.resume_interrupted(run_id)
    except (RunNotStartableError, DuplicateRunError) as exc:
        raise HTTPException(status_code=409, detail="Run 当前不可恢复") from exc
    except RuntimePreparationError as exc:
        raise HTTPException(status_code=409, detail=exc.public_message) from exc
    except RuntimeShuttingDownError as exc:
        raise HTTPException(status_code=503, detail="Agent Runtime 暂不可用") from exc
    db.refresh(run)
    return run


def _approval_payload(approval: AgentApproval) -> dict:
    return {
        "id": approval.id,
        "run_id": approval.run_id,
        "tool_call_id": approval.tool_call_id,
        "tool_name": approval.tool_name,
        "arguments": approval.arguments_json,
        "approved_arguments": (
            approval.decision_payload.get("approved_arguments")
            if approval.decision_payload else None
        ),
        "status": approval.status,
        "revision": approval.revision,
        "decision": approval.decision,
        "created_at": approval.created_at,
        "reviewed_at": approval.reviewed_at,
    }


@router.get("/runs/{run_id}/approvals")
def list_agent_approvals(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """刷新后从持久化快照恢复审批卡片，不依赖曾经收到的 SSE。"""
    if get_run_for_owner(db, run_id, current_user.id) is None:
        raise HTTPException(status_code=404, detail="Agent Run 不存在")
    approvals = db.scalars(
        select(AgentApproval)
        .where(AgentApproval.run_id == run_id)
        .order_by(AgentApproval.created_at.asc(), AgentApproval.id.asc())
    ).all()
    return [_approval_payload(approval) for approval in approvals]


@router.post("/runs/{run_id}/approvals/{approval_id}/decision")
async def decide_agent_approval(
    run_id: str,
    approval_id: str,
    body: ApprovalDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    runtime: AgentRuntimePort = Depends(get_agent_runtime),
):
    """用用户归属和 revision CAS 锁定一次决定；事件与决定同事务提交。"""
    # 与 prepare_approval、写工具统一先锁 Run 再锁 Approval，避免 MySQL 锁序反转。
    run = db.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.owner_id == current_user.id,
        ).with_for_update()
    )
    approval = db.scalar(
        select(AgentApproval).where(
            AgentApproval.id == approval_id,
            AgentApproval.run_id == run_id,
        ).with_for_update()
    ) if run is not None else None
    if approval is None:
        raise HTTPException(status_code=404, detail="审批不存在")
    if run.status != "waiting_approval":
        raise HTTPException(status_code=409, detail="Run 当前不在等待审批")
    new_status = "rejected" if body.decision is ApprovalDecisionType.REJECT else "approved"
    approved_arguments = approval.arguments_json
    if body.decision is ApprovalDecisionType.APPROVE:
        approved_arguments = _validated_approval_arguments(
            approval.tool_name, approval.arguments_json
        )
    if body.decision is ApprovalDecisionType.EDIT:
        approved_arguments = _validated_approval_arguments(
            approval.tool_name,
            {**approval.arguments_json, **(body.edited_arguments or {})},
        )
    approved_snapshot = (
        None if new_status == "rejected" else {
            "approved_arguments": approved_arguments,
            "arguments_hash": hash_arguments(approved_arguments),
        }
    )
    changed = db.execute(
        update(AgentApproval)
        .where(
            AgentApproval.id == approval_id,
            AgentApproval.run_id == run_id,
            AgentApproval.status == "pending",
            AgentApproval.revision == body.revision,
        )
        .values(
            status=new_status,
            decision=body.decision.value,
            decision_payload=approved_snapshot,
            revision=body.revision + 1,
            reviewed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="审批已处理或版本已变化")
    append_event(
        db,
        run_id=run_id,
        event_type="approval.resolved",
        payload_json={"approval_id": approval_id, "decision": body.decision.value},
    )
    db.commit()
    db.refresh(approval)
    # 审批事务先落库；后台恢复从数据库和 Checkpoint 验证，不信任请求体。
    try:
        runtime.resume(run_id)
    except (DuplicateRunError, RuntimeShuttingDownError) as exc:
        # 决定已提交，不能回滚；把未能调度的 Run 留作 M8 可识别的 interrupted。
        locked_run = db.scalar(
            select(AgentRun).where(
                AgentRun.id == run_id, AgentRun.owner_id == current_user.id
            ).with_for_update().execution_options(populate_existing=True)
        )
        if locked_run is not None and locked_run.status == RunStatus.WAITING_APPROVAL.value:
            ensure_run_transition(RunStatus.WAITING_APPROVAL, RunStatus.INTERRUPTED)
            locked_run.status = RunStatus.INTERRUPTED.value
            locked_run.error_code = "runtime_unavailable"
            locked_run.error_message = "审批已保存，但运行时未能调度恢复"
            append_event(
                db,
                run_id=run_id,
                event_type="run.interrupted",
                payload_json={
                    "error_code": locked_run.error_code,
                    "message": locked_run.error_message,
                },
            )
        db.commit()
        raise HTTPException(status_code=503, detail="审批已保存，但运行暂时中断") from exc
    return _approval_payload(approval)


def _to_event_envelope(event: EventRecord) -> EventEnvelope:
    return EventEnvelope(
        run_id=event.run_id,
        sequence=event.sequence,
        type=EventType(event.event_type),
        created_at=event.created_at,
        data=event.payload_json,
    )


@router.get("/runs/{run_id}/events", response_model=list[EventEnvelope])
def list_agent_events(
    run_id: str,
    after: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if get_run_for_owner(db, run_id, current_user.id) is None:
        raise HTTPException(status_code=404, detail="Agent Run 不存在")
    events = db.scalars(
        select(EventRecord)
        .where(EventRecord.run_id == run_id, EventRecord.sequence > after)
        .order_by(EventRecord.sequence.asc())
    ).all()
    return [_to_event_envelope(event) for event in events]


def _encode_sse_event(event: EventEnvelope) -> str:
    return (
        f"id: {event.sequence}\n"
        f"event: {event.type.value}\n"
        f"data: {event.model_dump_json()}\n\n"
    )


def _encode_sse_heartbeat(run_id: str) -> str:
    data = json.dumps({"run_id": run_id}, ensure_ascii=False, separators=(",", ":"))
    return f"event: heartbeat\ndata: {data}\n\n"


async def stream_agent_events(
    *,
    request: Request,
    run_id: str,
    owner_id: int,
    after: int,
    session_factory: AgentSessionFactory,
    poll_interval_seconds: float = 0.25,
    heartbeat_interval_seconds: float = 15.0,
) -> AsyncIterator[str]:
    """从持久化序号继续发送；断开连接只结束读取，不接触 Runtime task。"""
    last_sequence = after
    loop = asyncio.get_running_loop()
    last_heartbeat = loop.time()

    while not await request.is_disconnected():
        with session_factory() as session:
            run = get_run_for_owner(session, run_id, owner_id)
            if run is None:
                return
            status_value = run.status
            records = session.scalars(
                select(EventRecord)
                .where(
                    EventRecord.run_id == run_id,
                    EventRecord.sequence > last_sequence,
                )
                .order_by(EventRecord.sequence.asc())
            ).all()
            events = [_to_event_envelope(record) for record in records]

        for event in events:
            last_sequence = event.sequence
            yield _encode_sse_event(event)

        if status_value in TERMINAL_RUN_STATUSES:
            return

        now = loop.time()
        if now - last_heartbeat >= heartbeat_interval_seconds:
            yield _encode_sse_heartbeat(run_id)
            last_heartbeat = now
        await asyncio.sleep(poll_interval_seconds)


@router.get("/runs/{run_id}/stream")
@router.get("/runs/{run_id}/events/stream")
async def stream_agent_run_events(
    request: Request,
    run_id: str,
    after: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    session_factory: AgentSessionFactory = Depends(get_agent_session_factory),
):
    if get_run_for_owner(db, run_id, current_user.id) is None:
        raise HTTPException(status_code=404, detail="Agent Run 不存在")
    return StreamingResponse(
        stream_agent_events(
            request=request,
            run_id=run_id,
            owner_id=current_user.id,
            after=after,
            session_factory=session_factory,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
