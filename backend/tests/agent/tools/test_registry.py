import pytest

from app.agent.tools import READ_TOOL_REGISTRY
from app.agent.tools.base import ToolInput, ToolOutput, ToolPermission, ToolSpec
from app.agent.tools.registry import (
    DuplicateToolNameError,
    FrozenToolRegistryError,
    ToolPermissionError,
    ToolRegistry,
)


class LookupInput(ToolInput):
    query: str


class LookupOutput(ToolOutput):
    count: int


def _spec(name="lookup", permission=ToolPermission.READ):
    return ToolSpec(
        name=name,
        description="Lookup records",
        permission=permission,
        input_model=LookupInput,
        output_model=LookupOutput,
        handler=lambda _session, _context, _arguments: LookupOutput(count=0),
    )


def test_registry_rejects_duplicate_names():
    registry = ToolRegistry()
    registry.register(_spec())

    with pytest.raises(DuplicateToolNameError):
        registry.register(_spec())


def test_model_schemas_expose_only_model_input_contract():
    registry = ToolRegistry([_spec()])

    assert registry.names() == ("lookup",)
    assert registry.get("lookup").name == "lookup"
    assert registry.model_schemas() == [
        {
            "type": "function",
            "function": {
                "name": "lookup",
                "description": "Lookup records",
                "parameters": LookupInput.model_json_schema(),
            },
        }
    ]
    serialized = str(registry.model_schemas())
    assert "owner_id" not in serialized
    assert "run_id" not in serialized
    assert "output_model" not in serialized
    assert "handler" not in serialized


def test_read_tool_registry_matches_the_planned_allowlist_snapshot():
    expected = (
        "search_notes",
        "get_note",
        "list_tasks",
        "get_task",
        "lint_knowledge",
    )

    assert READ_TOOL_REGISTRY.names() == expected
    assert tuple(
        schema["function"]["name"] for schema in READ_TOOL_REGISTRY.model_schemas()
    ) == expected
    assert all(
        READ_TOOL_REGISTRY.get(name).permission is ToolPermission.READ for name in expected
    )
    registered = " ".join(expected).lower()
    assert all(forbidden not in registered for forbidden in ("delete", "sql", "http", "shell"))
    assert READ_TOOL_REGISTRY.is_frozen is True


def test_registry_can_reject_permissions_outside_its_policy():
    registry = ToolRegistry(allowed_permissions={ToolPermission.READ})

    with pytest.raises(ToolPermissionError):
        registry.register(_spec(permission=ToolPermission.WRITE))


def test_frozen_registry_rejects_further_registration():
    registry = ToolRegistry([_spec()])
    registry.freeze()

    with pytest.raises(FrozenToolRegistryError):
        registry.register(_spec("another"))
