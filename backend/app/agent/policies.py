"""Agent Run 的显式有限状态机，集中定义允许的生命周期迁移。"""

import hashlib
import json
from typing import Any

from pydantic import ConfigDict, JsonValue, TypeAdapter, ValidationError

from app.agent.schemas import RunStatus
from app.agent.tools.base import ToolPermission


class InvalidRunTransition(ValueError):
    pass


ALLOWED_RUN_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.QUEUED: frozenset({RunStatus.RUNNING}),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.WAITING_APPROVAL,
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.CANCELLING,
            RunStatus.INTERRUPTED,
        }
    ),
    RunStatus.WAITING_APPROVAL: frozenset(
        {
            RunStatus.RUNNING,
            RunStatus.CANCELLING,
            RunStatus.FAILED,
            RunStatus.INTERRUPTED,
        }
    ),
    RunStatus.INTERRUPTED: frozenset(
        {RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.CANCELLED}
    ),
    RunStatus.CANCELLING: frozenset({RunStatus.CANCELLED, RunStatus.FAILED}),
    RunStatus.COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
}
# completed、failed、cancelled 的空目标集合表示终态，后续写入不能使其重新运行。


def can_transition(source: RunStatus, target: RunStatus) -> bool:
    return target in ALLOWED_RUN_TRANSITIONS[source]


def ensure_run_transition(source: RunStatus, target: RunStatus) -> None:
    """在持久化状态前执行领域校验，非法跳转作为调用方错误显式失败。"""
    if not can_transition(source, target):
        raise InvalidRunTransition(f"cannot transition run from {source} to {target}")


def approval_required(permission: ToolPermission) -> bool:
    """未知权限默认拒绝，避免新工具绕过审批门禁。"""
    if permission is ToolPermission.READ:
        return False
    if permission is ToolPermission.WRITE:
        return True
    raise ValueError(f"unsupported tool permission: {permission}")


_ARGUMENTS = TypeAdapter(dict[str, JsonValue], config=ConfigDict(allow_inf_nan=False))


def canonical_arguments(arguments: dict[str, Any]) -> str:
    """审批与执行共用同一规范化形式；键顺序不能改变参数身份。"""
    try:
        validated = _ARGUMENTS.validate_python(arguments)
        return json.dumps(validated, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, ValidationError) as exc:
        raise ValueError("arguments must contain finite JSON values") from exc


def hash_arguments(arguments: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_arguments(arguments).encode("utf-8")).hexdigest()
