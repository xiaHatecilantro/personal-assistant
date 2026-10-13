from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint

from app.agent_models import AgentApproval, AgentEvent, AgentRun, AgentToolExecution
from app.config import Base
from app.models import User


def _foreign_key_contract(column) -> tuple[str, str | None]:
    foreign_key = next(iter(column.foreign_keys))
    return foreign_key.target_fullname, foreign_key.ondelete


def _index_columns(table) -> dict[str | None, tuple[str, ...]]:
    return {
        index.name: tuple(column.name for column in index.columns)
        for index in table.indexes
    }


def test_agent_run_metadata_matches_persistence_contract():
    table = AgentRun.__table__

    assert User.__table__ is Base.metadata.tables["users"]
    assert table is Base.metadata.tables["agent_runs"]
    assert set(table.columns.keys()) == {
        "id",
        "owner_id",
        "goal",
        "status",
        "thread_id",
        "graph_version",
        "max_steps",
        "timeout_seconds",
        "step_count",
        "final_answer",
        "error_code",
        "error_message",
        "cancel_requested_at",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    }
    assert isinstance(table.c.id.type, String)
    assert table.c.id.type.length == 36
    assert table.c.id.primary_key is True
    assert _foreign_key_contract(table.c.owner_id) == ("users.id", "CASCADE")
    assert isinstance(table.c.goal.type, Text)
    assert isinstance(table.c.status.type, String)
    assert isinstance(table.c.thread_id.type, String)
    assert table.c.thread_id.type.length == 36
    assert table.c.thread_id.unique is True

    indexes = _index_columns(table)
    assert indexes["ix_agent_runs_owner_status"] == ("owner_id", "status")
    assert indexes["ix_agent_runs_owner_created"] == ("owner_id", "created_at")


def test_agent_event_metadata_matches_append_only_event_contract():
    table = AgentEvent.__table__

    assert table is Base.metadata.tables["agent_events"]
    assert set(table.columns.keys()) == {
        "id",
        "run_id",
        "sequence",
        "event_type",
        "schema_version",
        "payload_json",
        "created_at",
    }
    assert isinstance(table.c.id.type, Integer)
    assert table.c.id.primary_key is True
    assert _foreign_key_contract(table.c.run_id) == ("agent_runs.id", "CASCADE")
    assert isinstance(table.c.sequence.type, Integer)
    assert isinstance(table.c.event_type.type, String)
    assert isinstance(table.c.schema_version.type, Integer)
    assert isinstance(table.c.payload_json.type, JSON)
    assert isinstance(table.c.created_at.type, DateTime)

    unique_constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert unique_constraints["uq_agent_events_run_sequence"] == ("run_id", "sequence")


def test_agent_approval_metadata_matches_review_contract():
    table = AgentApproval.__table__

    assert table is Base.metadata.tables["agent_approvals"]
    assert set(table.columns.keys()) == {
        "id",
        "run_id",
        "tool_call_id",
        "tool_name",
        "tool_version",
        "arguments_json",
        "arguments_hash",
        "status",
        "revision",
        "decision",
        "decision_payload",
        "reviewed_at",
        "created_at",
    }
    assert isinstance(table.c.id.type, String)
    assert table.c.id.type.length == 36
    assert table.c.id.primary_key is True
    assert _foreign_key_contract(table.c.run_id) == ("agent_runs.id", "CASCADE")
    assert isinstance(table.c.tool_call_id.type, String)
    assert isinstance(table.c.tool_name.type, String)
    assert isinstance(table.c.tool_version.type, String)
    assert isinstance(table.c.arguments_json.type, JSON)
    assert isinstance(table.c.arguments_hash.type, String)
    assert table.c.arguments_hash.type.length == 64
    assert isinstance(table.c.status.type, String)
    assert isinstance(table.c.revision.type, Integer)
    assert table.c.decision.nullable is True
    assert isinstance(table.c.decision_payload.type, JSON)
    assert table.c.decision_payload.nullable is True
    assert isinstance(table.c.reviewed_at.type, DateTime)
    assert table.c.reviewed_at.nullable is True

    unique_constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert unique_constraints["uq_agent_approvals_run_tool_call"] == (
        "run_id",
        "tool_call_id",
    )


def test_agent_tool_execution_metadata_matches_idempotent_execution_contract():
    table = AgentToolExecution.__table__

    assert table is Base.metadata.tables["agent_tool_executions"]
    assert set(table.columns.keys()) == {
        "id",
        "run_id",
        "tool_call_id",
        "arguments_hash",
        "status",
        "result_json",
        "business_entity_type",
        "business_entity_id",
        "duration_ms",
        "created_at",
        "finished_at",
    }
    assert isinstance(table.c.id.type, String)
    assert table.c.id.type.length == 36
    assert table.c.id.primary_key is True
    assert _foreign_key_contract(table.c.run_id) == ("agent_runs.id", "CASCADE")
    assert isinstance(table.c.tool_call_id.type, String)
    assert isinstance(table.c.arguments_hash.type, String)
    assert table.c.arguments_hash.type.length == 64
    assert isinstance(table.c.status.type, String)
    assert isinstance(table.c.result_json.type, JSON)
    assert table.c.result_json.nullable is True
    assert table.c.business_entity_type.nullable is True
    assert table.c.business_entity_id.nullable is True
    assert isinstance(table.c.duration_ms.type, Integer)
    assert table.c.duration_ms.nullable is True
    assert isinstance(table.c.created_at.type, DateTime)
    assert isinstance(table.c.finished_at.type, DateTime)
    assert table.c.finished_at.nullable is True

    unique_constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert unique_constraints["uq_agent_tool_executions_run_tool_call"] == (
        "run_id",
        "tool_call_id",
    )
