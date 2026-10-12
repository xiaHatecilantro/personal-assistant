"""M6 审批决定的用户隔离、版本 CAS 与事件事务测试。"""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.policies import hash_arguments
from app.agent_models import AgentApproval, AgentEvent, AgentRun
from app.auth import get_current_user
from app.config import Base, get_db
from app.models import User


@pytest.fixture()
def approval_api():
    from app.routers.agents import router

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    run_id = str(uuid4())
    with factory() as session:
        alice = User(username="approval-alice", password_hash="hash")
        bob = User(username="approval-bob", password_hash="hash")
        session.add_all([alice, bob])
        session.flush()
        owner_ids = {"alice": alice.id, "bob": bob.id}
        run = AgentRun(
            id=run_id,
            owner_id=alice.id,
            goal="创建任务",
            status="waiting_approval",
            thread_id=run_id,
            graph_version="read-v1",
            max_steps=3,
            timeout_seconds=60,
        )
        approval = AgentApproval(
            run_id=run_id,
            tool_call_id="call-1",
            tool_name="create_task",
            tool_version="v1",
            arguments_json={"title": "准备周报"},
            arguments_hash="a" * 64,
        )
        session.add_all([run, approval])
        session.commit()
        approval_id = approval.id

    current = {"owner_id": owner_ids["alice"], "resumes": []}
    app = FastAPI()
    app.include_router(router)

    class RuntimeStub:
        def resume(self, selected_run_id: str) -> None:
            # 调度必须发生在审批事务提交后，后台任务才能看到不可变决定快照。
            with factory() as session:
                recorded = session.get(AgentApproval, approval_id)
                assert recorded is not None and recorded.status != "pending"
            if current.get("fail_resume"):
                from app.agent.runtime import RuntimeShuttingDownError

                raise RuntimeShuttingDownError("shutdown")
            current["resumes"].append(selected_run_id)

    app.state.agent_runtime = RuntimeStub()

    def override_db():
        with factory() as session:
            yield session

    def override_user():
        with factory() as session:
            return session.get(User, current["owner_id"])

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    with TestClient(app) as client:
        yield client, factory, current, owner_ids, run_id, approval_id
    engine.dispose()


def test_approval_snapshot_is_owner_scoped(approval_api):
    client, _, current, owners, run_id, approval_id = approval_api
    url = f"/api/v1/agent/runs/{run_id}/approvals"
    response = client.get(url)
    assert response.status_code == 200
    assert [approval["id"] for approval in response.json()] == [approval_id]
    current["owner_id"] = owners["bob"]
    assert client.get(url).status_code == 404


def test_approve_revalidates_original_model_arguments(approval_api):
    client, factory, _, _, run_id, approval_id = approval_api
    with factory() as session:
        approval = session.get(AgentApproval, approval_id)
        approval.arguments_json = {"title": ""}
        session.commit()

    response = client.post(
        f"/api/v1/agent/runs/{run_id}/approvals/{approval_id}/decision",
        json={"decision": "approve", "revision": 1},
    )
    assert response.status_code == 422
    with factory() as session:
        assert session.get(AgentApproval, approval_id).status == "pending"


def test_runtime_shutdown_after_decision_leaves_a_recoverable_interrupted_run(approval_api):
    client, factory, current, _, run_id, approval_id = approval_api
    current["fail_resume"] = True

    response = client.post(
        f"/api/v1/agent/runs/{run_id}/approvals/{approval_id}/decision",
        json={"decision": "approve", "revision": 1},
    )

    assert response.status_code == 503
    with factory() as session:
        assert session.get(AgentApproval, approval_id).status == "approved"
        run = session.get(AgentRun, run_id)
        assert run.status == "interrupted"
        assert run.error_code == "runtime_unavailable"
        events = list(session.scalars(
            select(AgentEvent).where(AgentEvent.run_id == run_id).order_by(AgentEvent.sequence)
        ))
        assert [event.event_type for event in events] == ["approval.resolved", "run.interrupted"]


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_approval_decision_is_owner_scoped_and_single_use(approval_api, decision):
    client, factory, current, owners, run_id, approval_id = approval_api
    url = f"/api/v1/agent/runs/{run_id}/approvals/{approval_id}/decision"
    body = {"decision": decision, "revision": 1}

    current["owner_id"] = owners["bob"]
    assert client.post(url, json=body).status_code == 404
    current["owner_id"] = owners["alice"]

    response = client.post(url, json=body)
    assert response.status_code == 200
    assert response.json()["decision"] == decision
    assert response.json()["revision"] == 2
    assert current["resumes"] == [run_id]
    assert client.post(url, json=body).status_code == 409
    assert current["resumes"] == [run_id]

    with factory() as session:
        approval = session.get(AgentApproval, approval_id)
        assert approval is not None
        assert approval.status == ("approved" if decision == "approve" else "rejected")
        assert approval.decision == decision
        assert [
            event.event_type for event in session.scalars(
                select(AgentEvent).where(AgentEvent.run_id == run_id)
            )
        ] == ["approval.resolved"]


def test_edit_revalidates_arguments_and_freezes_approved_snapshot(approval_api):
    client, factory, _, _, run_id, approval_id = approval_api
    url = f"/api/v1/agent/runs/{run_id}/approvals/{approval_id}/decision"

    invalid = client.post(
        url,
        json={"decision": "edit", "revision": 1, "edited_arguments": {"title": ""}},
    )
    assert invalid.status_code == 422

    response = client.post(
        url,
        json={
            "decision": "edit",
            "revision": 1,
            "edited_arguments": {"title": "改为整理周报"},
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["arguments"] == {"title": "准备周报"}
    assert response.json()["approved_arguments"] == {"title": "改为整理周报"}

    with factory() as session:
        approval = session.get(AgentApproval, approval_id)
        assert approval is not None
        assert approval.arguments_json == {"title": "准备周报"}
        assert approval.decision_payload == {
            "approved_arguments": {"title": "改为整理周报"},
            "arguments_hash": hash_arguments({"title": "改为整理周报"}),
        }


def test_list_approvals_is_owner_scoped_and_exposes_pending_snapshot(approval_api):
    client, _, current, owners, run_id, approval_id = approval_api
    url = f"/api/v1/agent/runs/{run_id}/approvals"

    current["owner_id"] = owners["bob"]
    assert client.get(url).status_code == 404
    current["owner_id"] = owners["alice"]

    response = client.get(url)
    assert response.status_code == 200
    assert response.json() == [{
        "id": approval_id,
        "run_id": run_id,
        "tool_call_id": "call-1",
        "tool_name": "create_task",
        "arguments": {"title": "准备周报"},
        "approved_arguments": None,
        "status": "pending",
        "revision": 1,
        "decision": None,
        "created_at": response.json()[0]["created_at"],
        "reviewed_at": None,
    }]


def test_approve_revalidates_original_arguments_before_committing(approval_api):
    client, factory, current, _, run_id, approval_id = approval_api
    with factory() as session:
        approval = session.get(AgentApproval, approval_id)
        assert approval is not None
        approval.arguments_json = {"title": ""}
        session.commit()

    response = client.post(
        f"/api/v1/agent/runs/{run_id}/approvals/{approval_id}/decision",
        json={"decision": "approve", "revision": 1},
    )
    assert response.status_code == 422
    assert current["resumes"] == []
    with factory() as session:
        assert session.get(AgentApproval, approval_id).status == "pending"
        assert session.scalars(select(AgentEvent).where(AgentEvent.run_id == run_id)).all() == []
