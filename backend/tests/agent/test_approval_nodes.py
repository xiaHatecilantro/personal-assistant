"""审批 Graph 节点的幂等持久化与恢复边界。"""

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.agent.repository import create_run
from app.agent_models import AgentApproval, AgentEvent
from app.config import Base
from app.models import Note, Task, User


def test_prepare_approval_replay_keeps_one_approval_and_one_event() -> None:
    from app.agent.graph import prepare_approval

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(username="approval-owner", password_hash="hash")
        session.add(owner)
        session.flush()
        run = create_run(
            session,
            run_id="00000000-0000-0000-0000-000000000011",
            owner_id=owner.id,
            goal="创建任务",
            graph_version="write-v1",
            max_steps=3,
            timeout_seconds=60,
        )
        owner_id, run_id = owner.id, run.id
        session.commit()

    @contextmanager
    def session_factory():
        with Session(engine) as session:
            yield session

    state = {
        "run_id": run_id,
        "owner_id": owner_id,
        "pending_tool_call": {
            "id": "call-1",
            "name": "create_task",
            "arguments": {"title": "准备周报"},
        },
    }
    first = prepare_approval(state, session_factory=session_factory)
    replayed = prepare_approval(state, session_factory=session_factory)

    assert first == replayed
    assert first["pending_tool_call"]["approval_id"]
    assert first["pending_tool_call"]["arguments"] == {"title": "准备周报"}
    with Session(engine) as session:
        approval = session.scalar(select(AgentApproval))
        event = session.scalar(select(AgentEvent))
        assert approval.id == first["pending_tool_call"]["approval_id"]
        assert approval.tool_name == "create_task"
        assert approval.tool_version == "v1"
        assert approval.arguments_json == {"title": "准备周报"}
        assert event.event_type == "approval.required"
        assert event.payload_json["approval_id"] == approval.id
        assert session.scalar(select(func.count(AgentApproval.id))) == 1
        assert session.scalar(select(func.count(AgentEvent.id))) == 1
        assert session.scalar(select(func.count(Task.id))) == 0
        assert session.scalar(select(func.count(Note.id))) == 0
    engine.dispose()


def test_wait_approval_interrupts_with_persisted_identity_without_database(monkeypatch) -> None:
    from app.agent import graph

    captured = []
    monkeypatch.setattr(graph, "interrupt", lambda payload: captured.append(payload))
    state = {
        "run_id": "00000000-0000-0000-0000-000000000011",
        "owner_id": 7,
        "pending_tool_call": {
            "id": "call-1",
            "name": "create_task",
            "arguments": {"title": "准备周报"},
            "approval_id": "00000000-0000-0000-0000-000000000012",
        },
    }

    assert graph.wait_approval(state) == {}
    assert graph.wait_approval(state) == {}
    assert captured == [
        {"approval_id": "00000000-0000-0000-0000-000000000012", "tool_call_id": "call-1"},
        {"approval_id": "00000000-0000-0000-0000-000000000012", "tool_call_id": "call-1"},
    ]


def test_wait_approval_rejects_incomplete_checkpoint_before_interrupt(monkeypatch) -> None:
    from app.agent import graph

    monkeypatch.setattr(
        graph,
        "interrupt",
        lambda _payload: pytest.fail("incomplete approval must not interrupt"),
    )
    state = {"pending_tool_call": {"name": "create_task", "approval_id": "approval-1"}}

    with pytest.raises(ValueError, match="prepared approval"):
        graph.wait_approval(state)


@pytest.mark.parametrize(
    ("tool_name", "step_count", "expected"),
    [
        ("create_task", 0, "prepare_approval"),
        ("update_task", 0, "prepare_approval"),
        ("create_note", 0, "prepare_approval"),
        ("delete_task", 0, "execute_read"),
        ("create_task", 2, "finalize"),
    ],
)
def test_write_route_uses_allowlist_and_step_budget(tool_name, step_count, expected) -> None:
    from app.agent.graph import route_after_decide_with_approval

    state = {
        "step_count": step_count,
        "pending_tool_call": {"id": "call-1", "name": tool_name, "arguments": {}},
        "final_answer": None,
    }

    assert route_after_decide_with_approval(
        state, {"configurable": {"max_steps": 2}}
    ) == expected
