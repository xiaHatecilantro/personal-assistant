"""审批后的写工具只执行数据库中批准的参数，并持久化可重放结果。"""

from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.agent.policies import hash_arguments
from app.agent.tools.base import ToolContext, ToolPermission
from app.agent.tools.tasks import create_task_tool, execute_approved_write, update_task_tool
from app.agent_models import AgentApproval, AgentEvent, AgentRun, AgentToolExecution
from app.config import Base
from app.models import Note, Task, User


@pytest.fixture()
def write_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(username="write-owner", password_hash="hash")
        other = User(username="write-other", password_hash="hash")
        session.add_all([owner, other])
        session.flush()
        run_id = "00000000-0000-0000-0000-000000000091"
        session.add(
            AgentRun(
                id=run_id,
                owner_id=owner.id,
                goal="创建任务",
                status="running",
                thread_id=run_id,
                graph_version="write-v1",
                max_steps=3,
                timeout_seconds=60,
            )
        )
        session.commit()
        yield session, ToolContext(owner_id=owner.id, run_id=UUID(run_id)), other.id
    engine.dispose()


def _approval(session, context, tool_call_id, tool_name, arguments, *, status="approved"):
    session.add(
        AgentApproval(
            run_id=str(context.run_id),
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_version="v1",
            arguments_json={"title": "模型草稿"},
            arguments_hash=hash_arguments({"title": "模型草稿"}),
            status=status,
            decision="edit" if status == "approved" else "reject",
            decision_payload={
                "approved_arguments": arguments,
                "arguments_hash": hash_arguments(arguments),
            } if status == "approved" else None,
        )
    )
    session.commit()


def test_create_task_uses_approved_snapshot_and_replay_returns_original_result(write_db):
    session, context, _ = write_db
    _approval(session, context, "call-task-1", "create_task", {"title": "批准标题"})

    first = execute_approved_write(session, context, "call-task-1", "create_task")
    session.commit()
    replayed = execute_approved_write(session, context, "call-task-1", "create_task")
    session.commit()

    assert first == replayed
    assert first == {
        "tool_call_id": "call-task-1",
        "tool_name": "create_task",
        "ok": True,
        "result": {"task_id": first["result"]["task_id"]},
    }
    assert session.scalar(select(Task.title)) == "批准标题"
    assert session.scalar(select(func.count(Task.id))) == 1
    assert session.scalar(select(func.count(AgentToolExecution.id))) == 1
    assert [event.event_type for event in session.scalars(select(AgentEvent))] == [
        "tool.completed"
    ]


def test_rejected_approval_cannot_create_task(write_db):
    session, context, _ = write_db
    _approval(session, context, "call-task-2", "create_task", {"title": "拒绝标题"}, status="rejected")

    with pytest.raises(ValueError, match="approved"):
        execute_approved_write(session, context, "call-task-2", "create_task")

    assert session.scalar(select(func.count(Task.id))) == 0
    assert session.scalar(select(func.count(AgentToolExecution.id))) == 0


def test_approved_write_cannot_run_after_interruption(write_db):
    session, context, _ = write_db
    _approval(session, context, "call-after-stop", "create_task", {"title": "不应创建"})
    run = session.get(AgentRun, str(context.run_id))
    assert run is not None
    run.status = "interrupted"
    session.commit()

    with pytest.raises(ValueError, match="not running"):
        execute_approved_write(session, context, "call-after-stop", "create_task")

    assert session.scalar(select(func.count(Task.id))) == 0
    assert session.scalar(select(func.count(AgentToolExecution.id))) == 0
    assert session.scalar(select(func.count(AgentEvent.id))) == 0


def test_completed_effect_replays_without_new_write_after_run_stops(write_db):
    session, context, _ = write_db
    _approval(session, context, "call-replay", "create_task", {"title": "仅创建一次"})
    original = execute_approved_write(session, context, "call-replay", "create_task")
    session.commit()
    run = session.get(AgentRun, str(context.run_id))
    assert run is not None
    run.status = "interrupted"
    session.commit()

    replayed = execute_approved_write(session, context, "call-replay", "create_task")

    assert replayed == original
    assert session.scalar(select(func.count(Task.id))) == 1
    assert session.scalar(select(func.count(AgentToolExecution.id))) == 1
    assert session.scalar(select(func.count(AgentEvent.id))) == 1


def test_update_task_only_changes_owned_task(write_db):
    session, context, other_id = write_db
    own = Task(owner_id=context.owner_id, title="旧标题", priority="medium", status="todo", task_type="short_term")
    private = Task(owner_id=other_id, title="其他用户", priority="medium", status="todo", task_type="short_term")
    session.add_all([own, private])
    session.commit()
    _approval(session, context, "call-update-1", "update_task", {"task_id": own.id, "title": "新标题"})
    _approval(session, context, "call-update-2", "update_task", {"task_id": private.id, "title": "越权标题"})

    changed = execute_approved_write(session, context, "call-update-1", "update_task")
    denied = execute_approved_write(session, context, "call-update-2", "update_task")
    session.commit()

    assert changed["result"] == {"task_id": own.id}
    assert denied["error"]["code"] == "task_not_found"
    assert own.title == "新标题"
    assert private.title == "其他用户"
    assert [event.event_type for event in session.scalars(select(AgentEvent))] == [
        "tool.completed", "tool.failed"
    ]


def test_create_note_persists_approved_content_and_wikilinks(write_db):
    session, context, _ = write_db
    _approval(session, context, "call-note-1", "create_note", {
        "title": "Agent 复盘", "content": "关联 [[规划]] 与 [[规划]]", "tags": ["开发"]
    })

    result = execute_approved_write(session, context, "call-note-1", "create_note")
    session.commit()

    note = session.scalar(select(Note))
    assert result["result"] == {"note_id": note.id}
    assert note.owner_id == context.owner_id
    assert note.content == "关联 [[规划]] 与 [[规划]]"
    assert note.tags == '["开发"]'
    assert note.wikilinks == '["规划"]'


def test_approved_hash_mismatch_rejects_execution_without_side_effect(write_db):
    session, context, _ = write_db
    _approval(session, context, "call-tamper", "create_task", {"title": "获批标题"})
    approval = session.scalar(select(AgentApproval))
    approval.decision_payload = {
        "approved_arguments": {"title": "篡改标题"},
        "arguments_hash": hash_arguments({"title": "获批标题"}),
    }
    session.commit()

    with pytest.raises(ValueError, match="snapshot"):
        execute_approved_write(session, context, "call-tamper", "create_task")

    assert session.scalar(select(func.count(Task.id))) == 0
    assert session.scalar(select(func.count(AgentToolExecution.id))) == 0


def test_failed_business_write_replays_same_failure_without_extra_event(write_db):
    session, context, other_id = write_db
    private = Task(owner_id=other_id, title="私有", priority="medium", status="todo", task_type="short_term")
    session.add(private)
    session.commit()
    _approval(session, context, "call-private", "update_task", {
        "task_id": private.id, "title": "越权"
    })

    first = execute_approved_write(session, context, "call-private", "update_task")
    session.commit()
    replay = execute_approved_write(session, context, "call-private", "update_task")
    session.commit()

    assert first == replay
    assert first["ok"] is False
    assert first["error"]["code"] == "task_not_found"
    assert private.title == "私有"
    assert session.scalar(select(func.count(AgentToolExecution.id))) == 1
    assert session.scalar(select(func.count(AgentEvent.id))) == 1


def test_write_objects_execution_and_event_roll_back_together(write_db):
    session, context, _ = write_db
    _approval(session, context, "call-rollback", "create_task", {"title": "回滚任务"})

    assert execute_approved_write(session, context, "call-rollback", "create_task")["ok"]
    session.rollback()

    assert session.scalar(select(func.count(Task.id))) == 0
    assert session.scalar(select(func.count(AgentToolExecution.id))) == 0
    assert session.scalar(select(func.count(AgentEvent.id))) == 0


def test_note_tags_reject_blank_values():
    from app.agent.tools.notes import CreateNoteInput, create_note_tool

    with pytest.raises(ValidationError):
        CreateNoteInput(title="复盘", tags=[" "])
    for spec in (create_task_tool, update_task_tool, create_note_tool):
        assert spec.permission is ToolPermission.WRITE
        assert "owner_id" not in spec.input_model.model_json_schema()["properties"]
        assert "run_id" not in spec.input_model.model_json_schema()["properties"]
        assert "tool_call_id" not in spec.input_model.model_json_schema()["properties"]


def test_model_arguments_cannot_inject_owner_or_call_write_spec_directly(write_db):
    session, context, _ = write_db
    _approval(session, context, "call-extra", "create_task", {
        "title": "标题", "owner_id": 999
    })

    result = execute_approved_write(session, context, "call-extra", "create_task")
    session.commit()
    assert result["error"]["code"] == "invalid_arguments"
    assert session.scalar(select(func.count(Task.id))) == 0

    with pytest.raises(ValueError, match="approved"):
        create_task_tool.invoke(session, context, {"title": "绕过审批"})
    assert session.scalar(select(func.count(Task.id))) == 0


def test_create_task_rejects_parent_owned_by_another_user(write_db):
    session, context, other_id = write_db
    parent = Task(
        owner_id=other_id, title="私有父任务", priority="medium", status="todo", task_type="short_term"
    )
    session.add(parent)
    session.commit()
    _approval(session, context, "call-parent", "create_task", {
        "title": "越权子任务", "parent_id": parent.id
    })

    result = execute_approved_write(session, context, "call-parent", "create_task")
    session.commit()

    assert result["error"]["code"] == "parent_not_found"
    assert session.scalar(select(func.count(Task.id))) == 1


def test_write_execution_cannot_use_another_user_context(write_db):
    session, context, other_id = write_db
    _approval(session, context, "call-other", "create_task", {"title": "私有任务"})
    wrong_context = ToolContext(owner_id=other_id, run_id=context.run_id)

    with pytest.raises(ValueError, match="owner"):
        execute_approved_write(session, wrong_context, "call-other", "create_task")

    assert session.scalar(select(func.count(Task.id))) == 0
