"""Agent Run REST 接口的事务边界与租户隔离测试。"""

from dataclasses import dataclass, field
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


@dataclass
class ObservedRuntime:
    session_factory: sessionmaker
    started_run_ids: list[str] = field(default_factory=list)
    saw_committed_run: bool = False

    def start(self, run_id: str):
        from app.agent_models import AgentRun

        with self.session_factory() as session:
            self.saw_committed_run = session.get(AgentRun, run_id) is not None
        self.started_run_ids.append(run_id)
        return None


@pytest.fixture()
def runs_api():
    from app.routers.agents import get_agent_runtime, router

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        alice = User(username="agent-alice", password_hash="hash")
        bob = User(username="agent-bob", password_hash="hash")
        session.add_all([alice, bob])
        session.commit()
        alice_id, bob_id = alice.id, bob.id

    runtime = ObservedRuntime(session_factory)
    current_owner_id = {"value": alice_id}
    app = FastAPI()
    app.include_router(router)

    def override_db():
        with session_factory() as session:
            yield session

    def override_user():
        with session_factory() as session:
            return session.get(User, current_owner_id["value"])

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_agent_runtime] = lambda: runtime

    with TestClient(app) as client:
        yield client, session_factory, runtime, current_owner_id, alice_id, bob_id

    engine.dispose()


def test_create_run_commits_before_starting_background_execution(runs_api):
    client, session_factory, runtime, _, alice_id, _ = runs_api

    response = client.post("/api/v1/agent/runs", json={"goal": "汇总今天的未完成任务"})

    assert response.status_code == 202
    body = response.json()
    assert body["id"] == body["thread_id"]
    assert body["status"] == "queued"
    assert runtime.started_run_ids == [body["id"]]
    assert runtime.saw_committed_run is True
    with session_factory() as session:
        from app.agent_models import AgentRun

        persisted = session.get(AgentRun, body["id"])
        assert persisted is not None
        assert persisted.owner_id == alice_id


def test_list_runs_only_returns_current_owners_runs(runs_api):
    client, session_factory, _, current_owner_id, alice_id, bob_id = runs_api
    from app.agent_models import AgentRun

    alice_run_id = str(uuid4())
    bob_run_id = str(uuid4())
    with session_factory() as session:
        session.add_all(
            [
                AgentRun(
                    id=alice_run_id,
                    owner_id=alice_id,
                    goal="Alice goal",
                    thread_id=alice_run_id,
                    graph_version="read-v1",
                    max_steps=2,
                    timeout_seconds=30,
                ),
                AgentRun(
                    id=bob_run_id,
                    owner_id=bob_id,
                    goal="Bob goal",
                    thread_id=bob_run_id,
                    graph_version="read-v1",
                    max_steps=2,
                    timeout_seconds=30,
                ),
            ]
        )
        session.commit()

    current_owner_id["value"] = alice_id
    response = client.get("/api/v1/agent/runs")

    assert response.status_code == 200
    assert [run["id"] for run in response.json()] == [alice_run_id]


def test_run_detail_and_incremental_events_are_owner_scoped(runs_api):
    client, session_factory, _, current_owner_id, alice_id, bob_id = runs_api
    from app.agent_models import AgentEvent, AgentRun

    run_id = str(uuid4())
    with session_factory() as session:
        session.add(
            AgentRun(
                id=run_id,
                owner_id=alice_id,
                goal="Inspect events",
                thread_id=run_id,
                graph_version="read-v1",
                max_steps=2,
                timeout_seconds=30,
            )
        )
        session.flush()
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
                    payload_json={"goal": "Inspect events"},
                ),
            ]
        )
        session.commit()

    detail = client.get(f"/api/v1/agent/runs/{run_id}")
    events = client.get(f"/api/v1/agent/runs/{run_id}/events", params={"after": 1})

    assert detail.status_code == 200
    assert detail.json()["id"] == run_id
    assert events.status_code == 200
    assert [event["sequence"] for event in events.json()] == [2]
    assert events.json()[0]["type"] == "run.completed"
    assert events.json()[0]["data"] == {"final_answer": "done"}

    current_owner_id["value"] = bob_id
    assert client.get(f"/api/v1/agent/runs/{run_id}").status_code == 404
    assert client.get(f"/api/v1/agent/runs/{run_id}/events").status_code == 404
