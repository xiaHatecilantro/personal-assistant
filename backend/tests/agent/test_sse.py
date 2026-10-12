"""Agent 事件 SSE 的补发、心跳与连接生命周期测试。"""

import asyncio
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.config import Base, get_db
from app.models import User
from tests.agent.asyncio_utils import run_async


@pytest.fixture()
def sse_api():
    from app.agent_models import AgentEvent, AgentRun
    from app.routers.agents import get_agent_session_factory, router

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    completed_run_id = str(uuid4())
    running_run_id = str(uuid4())
    foreign_run_id = str(uuid4())
    with session_factory() as session:
        owner = User(username="sse-owner", password_hash="hash")
        foreign_owner = User(username="sse-foreign-owner", password_hash="hash")
        session.add_all([owner, foreign_owner])
        session.flush()
        owner_id = owner.id
        session.add_all(
            [
                AgentRun(
                    id=completed_run_id,
                    owner_id=owner_id,
                    goal="Completed stream",
                    status="completed",
                    thread_id=completed_run_id,
                    graph_version="read-v1",
                    max_steps=2,
                    timeout_seconds=30,
                ),
                AgentRun(
                    id=running_run_id,
                    owner_id=owner_id,
                    goal="Running stream",
                    status="running",
                    thread_id=running_run_id,
                    graph_version="read-v1",
                    max_steps=2,
                    timeout_seconds=30,
                ),
                AgentRun(
                    id=foreign_run_id,
                    owner_id=foreign_owner.id,
                    goal="Foreign stream",
                    status="completed",
                    thread_id=foreign_run_id,
                    graph_version="read-v1",
                    max_steps=2,
                    timeout_seconds=30,
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                AgentEvent(
                    run_id=completed_run_id,
                    sequence=1,
                    event_type="run.started",
                    payload_json={"goal": "Completed stream"},
                ),
                AgentEvent(
                    run_id=completed_run_id,
                    sequence=2,
                    event_type="run.completed",
                    payload_json={"final_answer": "done"},
                ),
            ]
        )
        session.commit()

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
    app.dependency_overrides[get_agent_session_factory] = lambda: session_factory
    with TestClient(app) as client:
        yield (
            client,
            session_factory,
            owner_id,
            completed_run_id,
            running_run_id,
            foreign_run_id,
        )

    engine.dispose()


def test_sse_reconnect_replays_only_events_after_sequence(sse_api):
    client, _, _, run_id, _, _ = sse_api

    response = client.get(f"/api/v1/agent/runs/{run_id}/events/stream", params={"after": 1})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "id: 1\n" not in response.text
    assert "id: 2\n" in response.text
    assert "event: run.completed\n" in response.text
    assert '"final_answer":"done"' in response.text


def test_planned_stream_path_is_alias_of_existing_sse_endpoint(sse_api):
    client, _, _, run_id, _, _ = sse_api
    response = client.get(f"/api/v1/agent/runs/{run_id}/stream", params={"after": 1})
    assert response.status_code == 200
    assert "id: 2\n" in response.text
    assert "id: 1\n" not in response.text


def test_sse_emits_json_heartbeat_while_run_is_active(sse_api):
    _, session_factory, owner_id, _, run_id, _ = sse_api
    from app.routers.agents import stream_agent_events

    class ConnectedRequest:
        async def is_disconnected(self) -> bool:
            return False

    async def first_chunk() -> str:
        stream = stream_agent_events(
            request=ConnectedRequest(),
            run_id=run_id,
            owner_id=owner_id,
            after=0,
            session_factory=session_factory,
            poll_interval_seconds=0,
            heartbeat_interval_seconds=0,
        )
        try:
            return await anext(stream)
        finally:
            await stream.aclose()

    chunk = run_async(first_chunk())

    assert "event: heartbeat\n" in chunk
    assert "id:" not in chunk
    assert f'"run_id":"{run_id}"' in chunk


def test_sse_endpoint_hides_other_owners_run(sse_api):
    client, _, _, _, _, foreign_run_id = sse_api

    response = client.get(f"/api/v1/agent/runs/{foreign_run_id}/events/stream")

    assert response.status_code == 404


def test_sse_disconnect_does_not_cancel_active_execution(sse_api):
    _, session_factory, owner_id, _, run_id, _ = sse_api
    from app.routers.agents import stream_agent_events

    class DisconnectedRequest:
        async def is_disconnected(self) -> bool:
            return True

    async def scenario() -> None:
        # Runtime task 与 SSE 生成器没有所有权关系；关闭读取连接不能传播取消。
        active_execution = asyncio.create_task(asyncio.Event().wait())
        stream = stream_agent_events(
            request=DisconnectedRequest(),
            run_id=run_id,
            owner_id=owner_id,
            after=0,
            session_factory=session_factory,
        )
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
        assert active_execution.done() is False
        active_execution.cancel()
        await asyncio.gather(active_execution, return_exceptions=True)

    run_async(scenario())


def test_sse_delivers_new_events_in_sequence_order(sse_api):
    _, session_factory, owner_id, _, run_id, _ = sse_api
    from app.agent_models import AgentEvent, AgentRun
    from app.routers.agents import stream_agent_events

    class ConnectedRequest:
        async def is_disconnected(self) -> bool:
            return False

    async def scenario() -> list[str]:
        stream = stream_agent_events(
            request=ConnectedRequest(),
            run_id=run_id,
            owner_id=owner_id,
            after=0,
            session_factory=session_factory,
            poll_interval_seconds=0.01,
            heartbeat_interval_seconds=3600,
        )
        first_chunk = asyncio.create_task(anext(stream))
        await asyncio.sleep(0)
        with session_factory() as session:
            run = session.get(AgentRun, run_id)
            assert run is not None
            run.status = "completed"
            session.add_all(
                [
                    AgentEvent(
                        run_id=run_id,
                        sequence=2,
                        event_type="run.completed",
                        payload_json={"final_answer": "done"},
                    ),
                    AgentEvent(
                        run_id=run_id,
                        sequence=1,
                        event_type="run.started",
                        payload_json={},
                    ),
                ]
            )
            session.commit()

        chunks = [await first_chunk, await anext(stream)]
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
        return chunks

    chunks = run_async(scenario())

    assert "id: 1\n" in chunks[0]
    assert "id: 2\n" in chunks[1]
