from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.policies import InvalidRunTransition
from app.agent.repository import (
    IdempotencyConflict,
    append_event,
    compare_and_set_status,
    create_approval,
    create_run,
    get_run_for_owner,
    record_tool_execution,
)
from app.agent.schemas import RunStatus
from app.agent_models import AgentApproval, AgentEvent, AgentRun, AgentToolExecution
from app.config import Base
from app.models import User


@pytest.fixture()
def database_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        owner = User(username="agent-owner", password_hash="hash")
        other_owner = User(username="other-owner", password_hash="hash")
        session.add_all([owner, other_owner])
        session.commit()
        yield session, owner.id, other_owner.id

    engine.dispose()


def _create_run(session, owner_id):
    run_id = str(uuid4())
    return create_run(
        session,
        run_id=run_id,
        owner_id=owner_id,
        goal="整理本周任务",
        graph_version="v1",
        max_steps=12,
        timeout_seconds=300,
    )


def test_create_and_get_run_are_owner_scoped_without_committing(database_session):
    session, owner_id, other_owner_id = database_session

    run = _create_run(session, owner_id)

    assert run.id is not None
    assert run.thread_id == run.id
    assert run.status == RunStatus.QUEUED.value
    assert session.get(AgentRun, run.id) is run
    assert get_run_for_owner(session, run.id, owner_id) is run
    assert get_run_for_owner(session, run.id, other_owner_id) is None

    run_id = run.id
    session.rollback()
    assert session.get(AgentRun, run_id) is None


def test_compare_and_set_status_is_atomic_owner_scoped_and_policy_guarded(database_session):
    session, owner_id, other_owner_id = database_session
    run = _create_run(session, owner_id)

    assert (
        compare_and_set_status(
            session,
            run_id=run.id,
            owner_id=owner_id,
            expected_status=RunStatus.QUEUED,
            new_status=RunStatus.RUNNING,
        )
        is True
    )
    session.refresh(run)
    assert run.status == RunStatus.RUNNING.value

    assert (
        compare_and_set_status(
            session,
            run_id=run.id,
            owner_id=owner_id,
            expected_status=RunStatus.QUEUED,
            new_status=RunStatus.RUNNING,
        )
        is False
    )
    assert (
        compare_and_set_status(
            session,
            run_id=run.id,
            owner_id=other_owner_id,
            expected_status=RunStatus.RUNNING,
            new_status=RunStatus.COMPLETED,
        )
        is False
    )

    with pytest.raises(InvalidRunTransition):
        compare_and_set_status(
            session,
            run_id=run.id,
            owner_id=owner_id,
            expected_status=RunStatus.RUNNING,
            new_status=RunStatus.QUEUED,
        )


def test_append_event_allocates_sequences_without_committing(database_session):
    session, owner_id, _ = database_session
    run = _create_run(session, owner_id)
    run_id = run.id
    session.commit()

    events = [
        append_event(
            session,
            run_id=run_id,
            event_type="run.started",
            payload_json={"position": position},
        )
        for position in range(1, 4)
    ]

    assert [event.sequence for event in events] == [1, 2, 3]

    session.rollback()
    assert session.scalar(select(func.count(AgentEvent.id))) == 0

    first = append_event(
        session,
        run_id=run_id,
        event_type="run.started",
        payload_json={},
    )
    session.add(
        AgentEvent(
            run_id=run_id,
            sequence=first.sequence,
            event_type="heartbeat",
            schema_version=1,
            payload_json={},
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_create_approval_is_idempotent_by_tool_call_and_arguments(database_session):
    session, owner_id, _ = database_session
    run = _create_run(session, owner_id)
    run_id = run.id
    session.commit()

    first = create_approval(
        session,
        run_id=run_id,
        tool_call_id="call-1",
        tool_name="create_task",
        tool_version="v1",
        arguments_json={"title": "准备周报"},
        arguments_hash="a" * 64,
    )
    repeated = create_approval(
        session,
        run_id=run_id,
        tool_call_id="call-1",
        tool_name="create_task",
        tool_version="v1",
        arguments_json={"title": "准备周报"},
        arguments_hash="a" * 64,
    )

    assert repeated is first
    assert session.scalar(select(func.count(AgentApproval.id))) == 1
    with pytest.raises(IdempotencyConflict):
        create_approval(
            session,
            run_id=run_id,
            tool_call_id="call-1",
            tool_name="create_task",
            tool_version="v1",
            arguments_json={"title": "另一任务"},
            arguments_hash="b" * 64,
        )

    session.rollback()
    assert session.scalar(select(func.count(AgentApproval.id))) == 0


def test_record_tool_execution_reuses_first_result_for_same_arguments(database_session):
    session, owner_id, _ = database_session
    run = _create_run(session, owner_id)
    run_id = run.id
    session.commit()

    first = record_tool_execution(
        session,
        run_id=run_id,
        tool_call_id="call-1",
        arguments_hash="a" * 64,
        status="completed",
        result_json={"task_id": 101},
        business_entity_type="task",
        business_entity_id="101",
        duration_ms=25,
    )
    repeated = record_tool_execution(
        session,
        run_id=run_id,
        tool_call_id="call-1",
        arguments_hash="a" * 64,
        status="completed",
        result_json={"task_id": 999},
        business_entity_type="task",
        business_entity_id="999",
        duration_ms=1,
    )

    assert repeated is first
    assert repeated.result_json == {"task_id": 101}
    assert session.scalar(select(func.count(AgentToolExecution.id))) == 1
    with pytest.raises(IdempotencyConflict):
        record_tool_execution(
            session,
            run_id=run_id,
            tool_call_id="call-1",
            arguments_hash="b" * 64,
            status="completed",
            result_json={"task_id": 102},
            business_entity_type="task",
            business_entity_id="102",
            duration_ms=20,
        )

    session.rollback()
    assert session.scalar(select(func.count(AgentToolExecution.id))) == 0


INVALID_JSON_VALUES = [
    pytest.param(object(), id="object"),
    pytest.param(float("nan"), id="nan"),
    pytest.param(float("inf"), id="inf"),
]


@pytest.mark.parametrize("invalid_value", INVALID_JSON_VALUES)
def test_append_event_rejects_non_json_payload_values(database_session, invalid_value):
    session, owner_id, _ = database_session
    run = _create_run(session, owner_id)
    run_id = run.id
    session.commit()

    with pytest.raises(ValidationError):
        append_event(
            session,
            run_id=run_id,
            event_type="run.started",
            payload_json={"value": invalid_value},
        )


@pytest.mark.parametrize("invalid_value", INVALID_JSON_VALUES)
def test_create_approval_rejects_non_json_payload_values(database_session, invalid_value):
    session, owner_id, _ = database_session
    run = _create_run(session, owner_id)
    run_id = run.id
    session.commit()

    with pytest.raises(ValidationError):
        create_approval(
            session,
            run_id=run_id,
            tool_call_id="invalid-approval",
            tool_name="create_task",
            tool_version="v1",
            arguments_json={"value": invalid_value},
            arguments_hash="a" * 64,
        )


@pytest.mark.parametrize("invalid_value", INVALID_JSON_VALUES)
def test_record_tool_execution_rejects_non_json_payload_values(
    database_session, invalid_value
):
    session, owner_id, _ = database_session
    run = _create_run(session, owner_id)
    run_id = run.id
    session.commit()

    with pytest.raises(ValidationError):
        record_tool_execution(
            session,
            run_id=run_id,
            tool_call_id="invalid-execution",
            arguments_hash="a" * 64,
            status="completed",
            result_json={"value": invalid_value},
            business_entity_type=None,
            business_entity_id=None,
            duration_ms=1,
        )
