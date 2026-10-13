"""M6 工具权限和审批参数快照的行为测试。"""

import pytest

from app.agent.tools import READ_TOOL_REGISTRY


def test_registered_read_tools_run_without_approval_and_writes_require_it() -> None:
    from app.agent.policies import approval_required
    from app.agent.tools.base import ToolPermission
    from app.agent.tools.notes import create_note_tool
    from app.agent.tools.tasks import create_task_tool, update_task_tool

    assert set(READ_TOOL_REGISTRY.names()) == {
        "search_notes", "get_note", "list_tasks", "get_task", "lint_knowledge"
    }
    assert all(
        approval_required(READ_TOOL_REGISTRY.get(name).permission) is False
        for name in READ_TOOL_REGISTRY.names()
    )
    assert approval_required(ToolPermission.WRITE) is True
    assert all(
        approval_required(tool.permission) is True
        for tool in (create_task_tool, update_task_tool, create_note_tool)
    )
    with pytest.raises(ValueError):
        approval_required("admin")


def test_approval_hash_uses_canonical_json_and_rejects_non_json_values() -> None:
    from app.agent.policies import canonical_arguments, hash_arguments

    first = {"title": "准备周报", "metadata": {"b": 2, "a": 1}}
    second = {"metadata": {"a": 1, "b": 2}, "title": "准备周报"}

    assert canonical_arguments(first) == canonical_arguments(second)
    assert hash_arguments(first) == hash_arguments(second)
    assert len(hash_arguments(first)) == 64
    with pytest.raises(ValueError):
        hash_arguments({"value": float("nan")})
