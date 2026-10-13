import json
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.agent.events import AgentEvent, EventType


def _event_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "run_id": str(uuid4()),
        "sequence": 1,
        "type": "run.started",
        "created_at": "2026-09-20T08:00:00Z",
        "data": {
            "goal": "整理本周任务",
            "metadata": {"source": "api", "tags": ["weekly", "planning"]},
        },
    }


def test_agent_event_has_stable_types_and_serializes_as_json():
    event = AgentEvent.model_validate(_event_payload())
    serialized = json.loads(event.model_dump_json())

    assert {event_type.value for event_type in EventType} == {
        "run.started",
        "plan.updated",
        "model.delta",
        "tool.proposed",
        "tool.started",
        "tool.completed",
        "tool.failed",
        "approval.required",
        "approval.resolved",
        "run.completed",
        "run.failed",
        "run.interrupted",
        "run.cancelled",
        "heartbeat",
    }
    assert event.schema_version == 1
    assert isinstance(event.run_id, UUID)
    assert isinstance(event.created_at, datetime)
    assert serialized == {
        "schema_version": 1,
        "run_id": str(event.run_id),
        "sequence": 1,
        "type": "run.started",
        "created_at": "2026-09-20T08:00:00Z",
        "data": {
            "goal": "整理本周任务",
            "metadata": {"source": "api", "tags": ["weekly", "planning"]},
        },
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": 2},
        {"run_id": "not-a-uuid"},
        {"sequence": 0},
        {"sequence": -1},
        {"type": "run.unknown"},
        {"data": {"value": object()}},
        {"data": {"value": float("nan")}},
        {"data": {"value": float("inf")}},
        {"data": {"value": float("-inf")}},
        {"unexpected": True},
    ],
)
def test_agent_event_rejects_invalid_envelope_or_non_json_data(changes):
    with pytest.raises(ValidationError):
        AgentEvent.model_validate({**_event_payload(), **changes})
