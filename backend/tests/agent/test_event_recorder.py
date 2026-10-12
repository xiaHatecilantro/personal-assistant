"""Graph 状态到稳定应用事件的边界测试。"""

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.agent.schemas import RunStatus
from app.agent_models import AgentEvent, AgentRun
from app.config import Base
from app.models import User


def _committed_run(session: Session) -> str:
    run_id = str(uuid4())
    owner = User(username=f"event-owner-{run_id}", password_hash="hash")
    session.add(owner)
    session.flush()
    session.add(
        AgentRun(
            id=run_id,
            owner_id=owner.id,
            goal="整理笔记",
            status=RunStatus.RUNNING.value,
            thread_id=run_id,
            graph_version="read-v1",
            max_steps=3,
            timeout_seconds=30,
        )
    )
    session.commit()
    return run_id


def test_record_graph_output_emits_only_stable_json_events() -> None:
    from app.agent.event_recorder import record_graph_output

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        run_id = _committed_run(session)
        raw_runtime_object = object()

        recorded = record_graph_output(
            session,
            run_id=run_id,
            output={
                "plan": ["搜索笔记", "汇总结果"],
                "observations": [
                    {
                        "tool_call_id": "call-1",
                        "tool_name": "search_notes",
                        "ok": True,
                        "result": {"items": [{"id": 1, "title": "TDD"}]},
                    },
                    {
                        "tool_call_id": "call-2",
                        "tool_name": "get_note",
                        "ok": False,
                        "error": {"code": "not_found", "message": "笔记不存在"},
                    },
                ],
                "step_count": 2,
                "final_answer": "已完成整理",
                "error": None,
                # LangGraph 内部对象即使出现在未公开字段，也不能穿透事件协议。
                "messages": [raw_runtime_object],
                "__metadata__": raw_runtime_object,
            },
        )
        session.commit()

        assert [event.event_type for event in recorded] == [
            "plan.updated",
            "tool.completed",
            "tool.failed",
            "run.completed",
        ]
        assert recorded[0].payload_json == {"items": ["搜索笔记", "汇总结果"]}
        assert recorded[-1].payload_json == {
            "final_answer": "已完成整理",
            "step_count": 2,
        }
        assert all("messages" not in event.payload_json for event in recorded)
        assert all("__metadata__" not in event.payload_json for event in recorded)
        for event in recorded:
            json.dumps(event.payload_json, allow_nan=False)

        persisted = list(
            session.scalars(
                select(AgentEvent)
                .where(AgentEvent.run_id == run_id)
                .order_by(AgentEvent.sequence)
            )
        )
        assert [event.sequence for event in persisted] == [1, 2, 3, 4]

    engine.dispose()


def test_record_graph_output_rejects_non_json_tool_result() -> None:
    from app.agent.event_recorder import record_graph_output

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        run_id = _committed_run(session)

        with pytest.raises(ValidationError):
            record_graph_output(
                session,
                run_id=run_id,
                output={
                    "observations": [
                        {
                            "tool_call_id": "call-1",
                            "tool_name": "search_notes",
                            "ok": True,
                            "result": {"raw": object()},
                        }
                    ],
                    "step_count": 1,
                    "final_answer": "ignored",
                    "error": None,
                },
            )

    engine.dispose()


def test_record_graph_output_skips_tool_event_already_committed_by_write_tool() -> None:
    from app.agent.event_recorder import record_graph_output
    from app.agent.repository import append_event

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        run_id = _committed_run(session)
        append_event(
            session,
            run_id=run_id,
            event_type="tool.completed",
            payload_json={"tool_call_id": "call-write", "tool_name": "create_task", "result": {}},
        )
        recorded = record_graph_output(
            session,
            run_id=run_id,
            output={
                "observations": [
                    {"tool_call_id": "call-write", "tool_name": "create_task", "ok": True, "result": {}},
                    {"tool_call_id": "call-read", "tool_name": "list_tasks", "ok": True, "result": {}},
                ],
                "step_count": 2,
                "final_answer": "完成",
                "error": None,
            },
        )
        session.commit()

        assert [event.event_type for event in recorded] == ["tool.completed", "run.completed"]
        events = list(session.scalars(
            select(AgentEvent).where(AgentEvent.run_id == run_id).order_by(AgentEvent.sequence)
        ))
        assert [event.sequence for event in events] == [1, 2, 3]
        assert [event.payload_json.get("tool_call_id") for event in events].count("call-write") == 1
    engine.dispose()
