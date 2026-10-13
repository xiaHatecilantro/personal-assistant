"""任务读写工具；写入仅消费数据库中的已批准参数。"""

from datetime import date, datetime
from time import monotonic
from typing import Any, Literal, Self

from pydantic import Field, ValidationError, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.events import EventType
from app.agent.schemas import RunStatus
from app.agent.tools.base import ToolContext, ToolInput, ToolOutput, ToolPermission, ToolSpec
from app.agent_models import AgentApproval, AgentRun, AgentToolExecution
from app.models import Task

TASK_LIST_MAX_LIMIT = 20


class ListTasksInput(ToolInput):
    status: Literal["todo", "in_progress", "done"] | None = None
    due_from: date | None = None
    due_to: date | None = None
    limit: int = Field(default=10, ge=1, le=TASK_LIST_MAX_LIMIT, strict=True)

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        if self.due_from and self.due_to and self.due_from > self.due_to:
            raise ValueError("due_from must not be after due_to")
        return self


class TaskSummary(ToolOutput):
    id: int
    title: str
    status: Literal["todo", "in_progress", "done"]
    priority: Literal["high", "medium", "low"]
    due_date: date | None
    tag: str | None
    task_type: Literal["short_term", "long_term", "daily"]
    created_at: datetime


class ListTasksOutput(ToolOutput):
    items: list[TaskSummary]
    count: int = Field(ge=0)


def list_tasks(
    session: Session,
    context: ToolContext,
    arguments: ListTasksInput,
) -> ListTasksOutput:
    stmt = select(Task).where(
        Task.owner_id == context.owner_id,
        Task.parent_id.is_(None),
    )
    if arguments.status:
        stmt = stmt.where(Task.status == arguments.status)
    if arguments.due_from:
        stmt = stmt.where(Task.due_date >= arguments.due_from)
    if arguments.due_to:
        stmt = stmt.where(Task.due_date <= arguments.due_to)
    stmt = stmt.order_by(
        Task.due_date.is_(None),
        Task.due_date.asc(),
        Task.created_at.desc(),
        Task.id.desc(),
    ).limit(arguments.limit)
    tasks = session.scalars(stmt).all()
    items = [
        TaskSummary(
            id=task.id,
            title=task.title,
            status=task.status,
            priority=task.priority,
            due_date=task.due_date,
            tag=task.tag,
            task_type=task.task_type,
            created_at=task.created_at,
        )
        for task in tasks
    ]
    return ListTasksOutput(items=items, count=len(items))


list_tasks_tool = ToolSpec(
    name="list_tasks",
    description="按状态和到期日列出当前用户的顶层任务。",
    permission=ToolPermission.READ,
    input_model=ListTasksInput,
    output_model=ListTasksOutput,
    handler=list_tasks,
)


class GetTaskInput(ToolInput):
    task_id: int = Field(gt=0, strict=True)


class SubtaskSummary(ToolOutput):
    id: int
    title: str
    status: Literal["todo", "in_progress", "done"]
    priority: Literal["high", "medium", "low"]
    due_date: date | None


class TaskDetail(ToolOutput):
    id: int
    title: str
    description: str | None
    priority: Literal["high", "medium", "low"]
    status: Literal["todo", "in_progress", "done"]
    due_date: date | None
    tag: str | None
    task_type: Literal["short_term", "long_term", "daily"]
    deadline_precision: Literal["day", "month", "year"] | None
    timer_preset: int | None
    timer_total_seconds: int
    created_at: datetime
    updated_at: datetime
    subtasks: list[SubtaskSummary]


class GetTaskOutput(ToolOutput):
    found: bool
    task: TaskDetail | None


def get_task(
    session: Session,
    context: ToolContext,
    arguments: GetTaskInput,
) -> GetTaskOutput:
    task = session.scalar(
        select(Task).where(
            Task.id == arguments.task_id,
            Task.owner_id == context.owner_id,
        )
    )
    if task is None:
        return GetTaskOutput(found=False, task=None)

    child_rows = session.scalars(
        select(Task)
        .where(
            Task.parent_id == task.id,
            Task.owner_id == context.owner_id,
        )
        .order_by(Task.created_at.asc(), Task.id.asc())
    ).all()
    subtasks = [
        SubtaskSummary(
            id=child.id,
            title=child.title,
            status=child.status,
            priority=child.priority,
            due_date=child.due_date,
        )
        for child in child_rows
    ]
    detail = TaskDetail(
        id=task.id,
        title=task.title,
        description=task.description,
        priority=task.priority,
        status=task.status,
        due_date=task.due_date,
        tag=task.tag,
        task_type=task.task_type,
        deadline_precision=task.deadline_precision,
        timer_preset=task.timer_preset,
        timer_total_seconds=task.timer_total_seconds or 0,
        created_at=task.created_at,
        updated_at=task.updated_at,
        subtasks=subtasks,
    )
    return GetTaskOutput(found=True, task=detail)


get_task_tool = ToolSpec(
    name="get_task",
    description="读取当前用户的一条任务及其子任务摘要。",
    permission=ToolPermission.READ,
    input_model=GetTaskInput,
    output_model=GetTaskOutput,
    handler=get_task,
)


class CreateTaskInput(ToolInput):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    priority: Literal["high", "medium", "low"] = "medium"
    status: Literal["todo", "in_progress", "done"] = "todo"
    due_date: date | None = None
    tag: str | None = Field(default=None, max_length=50)
    task_type: Literal["short_term", "long_term", "daily"] = "short_term"
    deadline_precision: Literal["day", "month", "year"] | None = None
    timer_preset: int | None = Field(default=None, ge=60, le=7200, strict=True)
    parent_id: int | None = Field(default=None, gt=0, strict=True)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be blank")
        return value


class CreateTaskOutput(ToolOutput):
    task_id: int


def _requires_approval(
    _session: Session, _context: ToolContext, _arguments: ToolInput
) -> ToolOutput:
    raise ValueError("write tools require a persisted approved tool call")


create_task_tool = ToolSpec(
    name="create_task",
    description="为当前用户创建任务；执行前必须人工审批。",
    permission=ToolPermission.WRITE,
    input_model=CreateTaskInput,
    output_model=CreateTaskOutput,
    handler=_requires_approval,
)


class UpdateTaskInput(ToolInput):
    task_id: int = Field(gt=0, strict=True)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    priority: Literal["high", "medium", "low"] | None = None
    status: Literal["todo", "in_progress", "done"] | None = None
    due_date: date | None = None
    tag: str | None = Field(default=None, max_length=50)
    task_type: Literal["short_term", "long_term", "daily"] | None = None
    deadline_precision: Literal["day", "month", "year"] | None = None
    timer_preset: int | None = Field(default=None, ge=60, le=7200, strict=True)

    @model_validator(mode="after")
    def require_valid_patch(self) -> Self:
        changed = self.model_fields_set - {"task_id"}
        if not changed:
            raise ValueError("at least one task field is required")
        for name in ("title", "priority", "status", "task_type"):
            if name in changed and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        if "title" in changed and not self.title.strip():
            raise ValueError("title must not be blank")
        return self


class UpdateTaskOutput(ToolOutput):
    task_id: int


update_task_tool = ToolSpec(
    name="update_task",
    description="修改当前用户的一条任务；执行前必须人工审批。",
    permission=ToolPermission.WRITE,
    input_model=UpdateTaskInput,
    output_model=UpdateTaskOutput,
    handler=_requires_approval,
)


def _create_task(session: Session, context: ToolContext, arguments: dict[str, Any]) -> dict[str, int]:
    parsed = CreateTaskInput.model_validate(arguments)
    if parsed.parent_id is not None:
        parent = session.scalar(
            select(Task).where(Task.id == parsed.parent_id, Task.owner_id == context.owner_id)
        )
        if parent is None:
            raise WriteBusinessError("parent_not_found", "父任务不存在")
    task = Task(owner_id=context.owner_id, **parsed.model_dump())
    session.add(task)
    session.flush()
    return CreateTaskOutput(task_id=task.id).model_dump()


def _update_task(session: Session, context: ToolContext, arguments: dict[str, Any]) -> dict[str, int]:
    parsed = UpdateTaskInput.model_validate(arguments)
    task = session.scalar(
        select(Task).where(Task.id == parsed.task_id, Task.owner_id == context.owner_id)
    )
    if task is None:
        raise WriteBusinessError("task_not_found", "任务不存在")
    for field, value in parsed.model_dump(exclude_unset=True, exclude={"task_id"}).items():
        setattr(task, field, value)
    session.flush()
    return UpdateTaskOutput(task_id=task.id).model_dump()


class WriteBusinessError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def execute_approved_write(
    session: Session,
    context: ToolContext,
    tool_call_id: str,
    tool_name: str,
) -> dict[str, Any]:
    """锁定 Run 后按已批准快照执行；调用方负责提交或回滚整个 Session。"""
    # policies 导入 tools.base 时会先初始化 tools 包，仓储依赖在此延后加载以避免循环导入。
    from app.agent.policies import hash_arguments
    from app.agent.repository import append_event, record_tool_execution

    if not tool_call_id or tool_name not in {"create_task", "update_task", "create_note"}:
        raise ValueError("unknown or missing write tool identity")
    run_id = str(context.run_id)
    run = session.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id, AgentRun.owner_id == context.owner_id
        ).with_for_update()
    )
    if run is None:
        raise ValueError("run does not belong to the current owner")
    approval = session.scalar(
        select(AgentApproval).where(
            AgentApproval.run_id == run_id,
            AgentApproval.tool_call_id == tool_call_id,
        ).with_for_update()
    )
    if (
        approval is None
        or approval.status != "approved"
        or approval.tool_name != tool_name
        or approval.tool_version != "v1"
        or not isinstance(approval.decision_payload, dict)
    ):
        raise ValueError("tool call has no matching approved decision")
    snapshot = approval.decision_payload
    arguments = snapshot.get("approved_arguments")
    approved_hash = snapshot.get("arguments_hash")
    if (
        not isinstance(arguments, dict)
        or not isinstance(approved_hash, str)
        or hash_arguments(arguments) != approved_hash
    ):
        raise ValueError("approved arguments snapshot is invalid")

    prior = session.scalar(
        select(AgentToolExecution).where(
            AgentToolExecution.run_id == run_id,
            AgentToolExecution.tool_call_id == tool_call_id,
        ).with_for_update()
    )
    if prior is not None:
        if prior.arguments_hash != approved_hash or prior.result_json is None:
            raise ValueError("tool call execution conflicts with approved arguments")
        return prior.result_json

    # 只限制新的业务副作用；已提交结果在 Checkpoint 重放时仍允许只读返回。
    if run.status != RunStatus.RUNNING.value or run.cancel_requested_at is not None:
        raise ValueError("run is not running or is cancelling")

    started_at = monotonic()
    try:
        if tool_name == "create_task":
            result = _create_task(session, context, arguments)
            entity_type, entity_id = "task", result["task_id"]
        elif tool_name == "update_task":
            result = _update_task(session, context, arguments)
            entity_type, entity_id = "task", result["task_id"]
        elif tool_name == "create_note":
            from app.agent.tools.notes import create_approved_note

            result = create_approved_note(session, context, arguments)
            entity_type, entity_id = "note", result["note_id"]
        else:
            raise ValueError("write tool is not implemented")
    except ValidationError:
        failure = WriteBusinessError("invalid_arguments", "工具参数校验失败")
    except WriteBusinessError as exc:
        failure = exc
    else:
        failure = None

    observation: dict[str, Any] = {
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "ok": failure is None,
    }
    if failure is None:
        observation["result"] = result
    else:
        observation["error"] = {"code": failure.code, "message": str(failure)}
    record_tool_execution(
        session,
        run_id=run_id,
        tool_call_id=tool_call_id,
        arguments_hash=approved_hash,
        status="completed" if failure is None else "failed",
        result_json=observation,
        business_entity_type=entity_type if failure is None else None,
        business_entity_id=str(entity_id) if failure is None else None,
        duration_ms=max(0, round((monotonic() - started_at) * 1000)),
    )
    append_event(
        session,
        run_id=run_id,
        event_type=(EventType.TOOL_COMPLETED if failure is None else EventType.TOOL_FAILED).value,
        payload_json=observation,
    )
    return observation
