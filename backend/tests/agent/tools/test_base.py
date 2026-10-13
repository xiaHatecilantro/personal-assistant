from uuid import UUID

import pytest
from pydantic import ValidationError

from app.agent.tools.base import (
    ToolContext,
    ToolInput,
    ToolOutput,
    ToolPermission,
    ToolSpec,
)


class EchoInput(ToolInput):
    text: str


class EchoOutput(ToolOutput):
    text: str


def test_tool_input_rejects_extra_fields_and_has_no_internal_context():
    with pytest.raises(ValidationError):
        EchoInput.model_validate({"text": "hello", "owner_id": 9})

    assert "owner_id" not in EchoInput.model_json_schema()["properties"]
    assert "run_id" not in EchoInput.model_json_schema()["properties"]


def test_tool_spec_injects_context_and_session_outside_model_arguments():
    calls = []

    def echo(session, context, arguments):
        calls.append((session, context, arguments))
        return EchoOutput(text=arguments.text)

    spec = ToolSpec(
        name="echo",
        description="Echo text",
        permission=ToolPermission.READ,
        input_model=EchoInput,
        output_model=EchoOutput,
        handler=echo,
    )
    context = ToolContext(
        owner_id=7,
        run_id=UUID("00000000-0000-0000-0000-000000000001"),
    )
    session = object()

    result = spec.invoke(session, context, {"text": "hello"})

    assert result == EchoOutput(text="hello")
    assert calls == [(session, context, EchoInput(text="hello"))]


def test_tool_output_does_not_coerce_wrong_primitive_types():
    with pytest.raises(ValidationError):
        EchoOutput(text=123)
