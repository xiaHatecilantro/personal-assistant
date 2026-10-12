"""M8 权限矩阵：运行、事件、审批与工具都以服务端 owner 为边界。"""

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.tools.base import ToolContext
from app.agent.tools.notes import get_note_tool
from app.agent.tools.tasks import execute_approved_write, get_task_tool
from app.agent_models import AgentApproval, AgentEvent, AgentRun
from app.auth import get_current_user
from app.config import Base, get_db
from app.models import Note, Task, User
from app.routers.agents import router


@pytest.fixture()
def security_api():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    run_id = str(uuid4())
    with factory() as session:
        alice = User(username="matrix-alice", password_hash="hash")
        bob = User(username="matrix-bob", password_hash="hash")
        session.add_all([alice, bob])
        session.flush()
        ids = {"alice": alice.id, "bob": bob.id}
        run = AgentRun(
            id=run_id,
            owner_id=bob.id,
            goal="Bob 的私有任务",
            status="waiting_approval",
            thread_id=run_id,
            graph_version="write-v1",
            max_steps=2,
            timeout_seconds=60,
        )
        approval = AgentApproval(
            run_id=run_id,
            tool_call_id="bob-call",
            tool_name="create_task",
            tool_version="v1",
            arguments_json={"title": "Bob 的任务"},
            arguments_hash="a" * 64,
        )
        session.add_all([
            run,
            approval,
            AgentEvent(run_id=run_id, sequence=1, event_type="run.started", payload_json={}),
            Task(owner_id=bob.id, title="Bob 的已有任务"),
            Note(owner_id=bob.id, title="Bob 的私有笔记", content="私有内容"),
        ])
        session.commit()
        approval_id = approval.id
        task_id = session.scalar(select(Task.id))
        note_id = session.scalar(select(Note.id))

    current = {"owner_id": ids["bob"]}
    app = FastAPI()
    app.include_router(router)

    class RuntimeStub:
        def __init__(self):
            self.recovered = []

        def resume(self, run_id: str) -> None:
            return None

        def resume_interrupted(self, run_id: str) -> None:
            self.recovered.append(run_id)
            with factory() as session:
                session.get(AgentRun, run_id).status = "running"
                session.commit()

    runtime = RuntimeStub()
    app.state.agent_runtime = runtime

    def override_db():
        with factory() as session:
            yield session

    def override_user():
        with factory() as session:
            return session.get(User, current["owner_id"])

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as client:
        yield client, factory, current, ids, run_id, approval_id, task_id, note_id, runtime
    engine.dispose()


def test_foreign_run_event_and_approval_paths_hide_existence(security_api):
    client, _, current, ids, run_id, approval_id, _, _, _ = security_api
    assert client.get(f"/api/v1/agent/runs/{run_id}").status_code == 200
    current["owner_id"] = ids["alice"]
    assert client.get("/api/v1/agent/runs").json() == []

    for suffix in ("", "/events", "/approvals", "/events/stream", "/stream"):
        foreign = client.get(f"/api/v1/agent/runs/{run_id}{suffix}")
        absent = client.get(f"/api/v1/agent/runs/{uuid4()}{suffix}")
        assert foreign.status_code == absent.status_code == 404
        assert foreign.json() == absent.json()

    decision = client.post(
        f"/api/v1/agent/runs/{run_id}/approvals/{approval_id}/decision",
        json={"decision": "approve", "revision": 1},
    )
    assert decision.status_code == 404
    for action in ("cancel", "resume"):
        foreign = client.post(f"/api/v1/agent/runs/{run_id}/{action}")
        absent = client.post(f"/api/v1/agent/runs/{uuid4()}/{action}")
        assert foreign.status_code == absent.status_code == 404
        assert foreign.json() == absent.json()


def test_foreign_tool_reads_and_write_execution_do_not_cross_owner(security_api):
    _, factory, _, ids, run_id, _, task_id, note_id, _ = security_api
    context = ToolContext(owner_id=ids["alice"], run_id=UUID(run_id))
    with factory() as session:
        assert get_task_tool.invoke(session, context, {"task_id": task_id}).found is False
        assert get_note_tool.invoke(session, context, {"note_id": note_id}).found is False
        with pytest.raises(ValueError, match="owner"):
            execute_approved_write(session, context, "bob-call", "create_task")
        assert session.scalar(select(Task.title).where(Task.id == task_id)) == "Bob 的已有任务"


def test_owner_can_explicitly_resume_interrupted_run(security_api):
    client, factory, current, ids, _, _, _, _, runtime = security_api
    run_id = str(uuid4())
    with factory() as session:
        session.add(AgentRun(
            id=run_id, owner_id=ids["alice"], goal="断点恢复", status="interrupted",
            thread_id=run_id, graph_version="write-v1", max_steps=2, timeout_seconds=60,
        ))
        session.commit()
    current["owner_id"] = ids["alice"]

    response = client.post(f"/api/v1/agent/runs/{run_id}/resume")

    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert runtime.recovered == [run_id]
