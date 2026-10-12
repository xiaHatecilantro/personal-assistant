"""M6/M7 门禁：真实 Graph、Runtime 与 HTTP 审批接口协同。"""

import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.agent.graph import compile_write_graph
from app.agent.model_gateway import FinalDecision, ModelToolCall, ToolDecision
from app.agent.runtime import AgentRuntime
from app.agent_models import AgentEvent, AgentToolExecution
from app.auth import get_current_user
from app.config import Base, get_db
from app.models import Task, User
from app.routers.agents import get_agent_runtime, router
from tests.agent.fakes import ScriptedModelGateway


def _wait_for_status(client: TestClient, run_id: str, target: str) -> dict:
    for _ in range(100):
        response = client.get(f"/api/v1/agent/runs/{run_id}")
        assert response.status_code == 200
        detail = response.json()
        if detail["status"] == target:
            return detail
        if detail["status"] == "failed":
            raise AssertionError(f"Run failed before {target}: {detail}")
        time.sleep(0.02)
    raise AssertionError(f"Run did not reach {target}")


def test_approval_edit_resumes_same_run_and_creates_one_task(tmp_path: Path) -> None:
    # 使用文件型 SQLite，让 TestClient 和 Graph 线程拥有独立连接与同一数据库。
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'flow.db').as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        owner = User(username="flow-owner", password_hash="hash")
        session.add(owner)
        session.commit()
        owner_id = owner.id

    graph = compile_write_graph(
        model_gateway=ScriptedModelGateway(
            [
                ToolDecision(
                    tool_call=ModelToolCall(
                        id="call-flow-1",
                        name="create_task",
                        arguments={"title": "模型建议"},
                    )
                ),
                FinalDecision(final_answer="任务已创建"),
            ]
        ),
        session_factory=session_factory,
        checkpointer=InMemorySaver(),
    )
    runtime = AgentRuntime(session_factory=session_factory, graphs={"write-v1": graph})
    app = FastAPI()
    app.include_router(router)

    def override_db():
        with session_factory() as session:
            yield session

    def override_user():
        with session_factory() as session:
            return session.get(User, owner_id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_agent_runtime] = lambda: runtime

    with TestClient(app) as client:
        response = client.post("/api/v1/agent/runs", json={"goal": "创建一条任务"})
        assert response.status_code == 202
        run_id = response.json()["id"]
        assert response.json()["graph_version"] == "write-v1"

        waiting = _wait_for_status(client, run_id, "waiting_approval")
        assert waiting["finished_at"] is None
        approvals_response = client.get(f"/api/v1/agent/runs/{run_id}/approvals")
        assert approvals_response.status_code == 200
        approvals = approvals_response.json()
        assert len(approvals) == 1
        assert approvals[0]["status"] == "pending"
        with session_factory() as session:
            assert session.scalar(select(func.count(Task.id))) == 0

        approval_id = approvals[0]["id"]
        decision = client.post(
            f"/api/v1/agent/runs/{run_id}/approvals/{approval_id}/decision",
            json={
                "decision": "edit",
                "revision": approvals[0]["revision"],
                "edited_arguments": {"title": "人工确认的标题"},
            },
        )
        assert decision.status_code == 200
        assert decision.json()["approved_arguments"]["title"] == "人工确认的标题"

        completed = _wait_for_status(client, run_id, "completed")
        assert completed["final_answer"] == "任务已创建"
        events_response = client.get(f"/api/v1/agent/runs/{run_id}/events")
        assert events_response.status_code == 200
        events = events_response.json()
        assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
        assert [event["type"] for event in events].count("tool.completed") == 1
        with session_factory() as session:
            assert session.scalar(select(Task.title)) == "人工确认的标题"
            assert session.scalar(select(func.count(Task.id))) == 1
            assert session.scalar(select(func.count(AgentToolExecution.id))) == 1
            assert session.scalar(select(func.count(AgentEvent.id))) == len(events)

    engine.dispose()
