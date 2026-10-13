"""M8 协作取消：持久化意图、用户隔离和运行时收敛。"""

import asyncio
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.schemas import RunStatus
from app.agent_models import AgentEvent, AgentRun
from app.auth import get_current_user
from app.config import Base, get_db
from app.models import User
from tests.agent.asyncio_utils import run_async


@pytest.fixture()
def cancel_api():
    from app.agent.runtime import AgentRuntime
    from app.routers.agents import router

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    ids = {status: str(uuid4()) for status in ("running", "waiting_approval", "interrupted", "completed")}
    with factory() as session:
        alice = User(username="cancel-alice", password_hash="hash")
        bob = User(username="cancel-bob", password_hash="hash")
        session.add_all([alice, bob])
        session.flush()
        owner_ids = {"alice": alice.id, "bob": bob.id}
        for run_status, run_id in ids.items():
            session.add(AgentRun(
                id=run_id,
                owner_id=alice.id,
                goal="取消测试",
                status=run_status,
                thread_id=run_id,
                graph_version="read-v1",
                max_steps=3,
                timeout_seconds=30,
            ))
        session.commit()

    runtime = AgentRuntime(session_factory=factory, graphs={})
    current = {"owner_id": owner_ids["alice"]}
    app = FastAPI()
    app.include_router(router)
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
        yield client, factory, current, owner_ids, ids
    engine.dispose()


def test_cancel_running_run_records_intent_and_repeated_request_is_idempotent(cancel_api):
    client, factory, _, _, ids = cancel_api
    run_id = ids["running"]
    url = f"/api/v1/agent/runs/{run_id}/cancel"

    response = client.post(url)
    repeated = client.post(url)

    assert response.status_code == repeated.status_code == 200
    assert response.json()["status"] == repeated.json()["status"] == "cancelled"
    with factory() as session:
        run = session.get(AgentRun, run_id)
        assert run.cancel_requested_at is not None
        assert run.finished_at is not None
        assert [event.event_type for event in session.scalars(
            select(AgentEvent).where(AgentEvent.run_id == run_id)
        )] == ["run.cancelled"]


def test_cancel_waiting_approval_finalizes_without_resuming_graph(cancel_api):
    client, factory, _, _, ids = cancel_api
    run_id = ids["waiting_approval"]

    response = client.post(f"/api/v1/agent/runs/{run_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    with factory() as session:
        assert session.get(AgentRun, run_id).status == RunStatus.CANCELLED.value


def test_cancel_other_users_run_returns_404_without_mutation(cancel_api):
    client, factory, current, owners, ids = cancel_api
    current["owner_id"] = owners["bob"]
    run_id = ids["running"]

    response = client.post(f"/api/v1/agent/runs/{run_id}/cancel")

    assert response.status_code == 404
    with factory() as session:
        run = session.get(AgentRun, run_id)
        assert run.status == RunStatus.RUNNING.value
        assert run.cancel_requested_at is None


def test_cancel_completed_run_is_idempotent_and_preserves_result(cancel_api):
    client, factory, _, _, ids = cancel_api
    run_id = ids["completed"]

    response = client.post(f"/api/v1/agent/runs/{run_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    with factory() as session:
        run = session.get(AgentRun, run_id)
        assert run.cancel_requested_at is None
        assert session.scalars(select(AgentEvent).where(AgentEvent.run_id == run_id)).all() == []


def test_cancel_interrupted_run_finishes_without_replaying_checkpoint(cancel_api):
    client, factory, _, _, ids = cancel_api
    run_id = ids["interrupted"]

    response = client.post(f"/api/v1/agent/runs/{run_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    with factory() as session:
        run = session.get(AgentRun, run_id)
        assert run.cancel_requested_at is not None
        assert run.finished_at is not None
        assert [event.event_type for event in session.scalars(
            select(AgentEvent).where(AgentEvent.run_id == run_id)
        )] == ["run.cancelled"]


def test_running_task_cancelled_after_persisted_request_finishes_as_cancelled(tmp_path):
    from app.agent.runtime import AgentRuntime

    database_path = tmp_path / "cancel.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    run_id = str(uuid4())
    with factory() as session:
        owner = User(username="active-cancel", password_hash="hash")
        session.add(owner)
        session.flush()
        session.add(AgentRun(
            id=run_id, owner_id=owner.id, goal="运行中取消", status="queued",
            thread_id=run_id, graph_version="read-v1", max_steps=3, timeout_seconds=30,
        ))
        session.commit()

    class BlockingGraph:
        def __init__(self):
            self.started = asyncio.Event()

        async def ainvoke(self, initial_state, *, config):
            self.started.set()
            await asyncio.Event().wait()

    graph = BlockingGraph()

    async def scenario():
        runtime = AgentRuntime(session_factory=factory, graphs={"read-v1": graph})
        task = runtime.start(run_id)
        await graph.started.wait()
        with factory() as session:
            run = session.get(AgentRun, run_id)
            run.status = "cancelling"
            from datetime import datetime, timezone
            run.cancel_requested_at = datetime.now(timezone.utc).replace(tzinfo=None)
            session.commit()
        runtime.request_cancel(run_id)
        with pytest.raises(asyncio.CancelledError):
            await task

    run_async(scenario())
    with factory() as session:
        run = session.get(AgentRun, run_id)
        assert run.status == "cancelled"
        assert run.finished_at is not None
        assert [event.event_type for event in session.scalars(
            select(AgentEvent).where(AgentEvent.run_id == run_id).order_by(AgentEvent.sequence)
        )] == ["run.started", "run.cancelled"]
    engine.dispose()


def test_graph_does_not_accept_model_result_after_cancel_request(tmp_path):
    from datetime import datetime, timezone

    from app.agent.graph import RunCancellationRequested, build_graph_config, compile_read_graph
    from app.agent.model_gateway import FinalDecision

    database_path = tmp_path / "graph-cancel.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    run_id = str(uuid4())
    with factory() as session:
        owner = User(username="graph-cancel", password_hash="hash")
        session.add(owner)
        session.flush()
        owner_id = owner.id
        session.add(AgentRun(
            id=run_id, owner_id=owner_id, goal="取消模型决策", status="running",
            thread_id=run_id, graph_version="read-v1", max_steps=3, timeout_seconds=30,
        ))
        session.commit()

    class CancellingGateway:
        async def decide(self, *, messages, tools):
            with factory() as session:
                run = session.get(AgentRun, run_id)
                run.status = "cancelling"
                run.cancel_requested_at = datetime.now(timezone.utc).replace(tzinfo=None)
                session.commit()
            return FinalDecision(final_answer="不应使用这个结果")

    graph = compile_read_graph(model_gateway=CancellingGateway(), session_factory=factory)
    state = {
        "run_id": run_id, "owner_id": owner_id, "goal": "取消模型决策",
        "step_count": 0, "plan": [], "messages": [], "pending_tool_call": None,
        "observations": [], "final_answer": None, "error": None,
    }
    with pytest.raises(RunCancellationRequested):
        run_async(graph.ainvoke(state, config=build_graph_config(run_id=run_id, max_steps=3)))
    engine.dispose()


def test_runtime_run_detail_redacts_credential_from_graph_result(tmp_path):
    from app.agent.runtime import AgentRuntime

    database_path = tmp_path / "redact-detail.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    run_id = str(uuid4())
    with factory() as session:
        owner = User(username="detail-redact", password_hash="hash")
        session.add(owner)
        session.flush()
        session.add(AgentRun(
            id=run_id, owner_id=owner.id, goal="测试脱敏", status="running",
            thread_id=run_id, graph_version="read-v1", max_steps=3, timeout_seconds=30,
        ))
        session.commit()

    runtime = AgentRuntime(session_factory=factory, graphs={})
    runtime._persist_result(run_id, {
        "step_count": 1, "observations": [], "plan": [],
        "final_answer": "authorization: Bearer example-secret", "error": None,
    })
    with factory() as session:
        run = session.get(AgentRun, run_id)
        assert "example-secret" not in run.final_answer
        assert "[REDACTED]" in run.final_answer
    engine.dispose()


def test_late_approval_interrupt_after_cancel_request_converges_to_cancelled(cancel_api):
    _, factory, _, _, ids = cancel_api
    run_id = ids["running"]
    with factory() as session:
        from datetime import datetime, timezone

        run = session.get(AgentRun, run_id)
        run.status = "cancelling"
        run.cancel_requested_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.commit()

    from app.agent.runtime import AgentRuntime

    runtime = AgentRuntime(session_factory=factory, graphs={})
    runtime._mark_waiting(run_id, {"pending_tool_call": {"approval_id": "stale"}})

    with factory() as session:
        assert session.get(AgentRun, run_id).status == "cancelled"
        assert [event.event_type for event in session.scalars(
            select(AgentEvent).where(AgentEvent.run_id == run_id)
        )] == ["run.cancelled"]
