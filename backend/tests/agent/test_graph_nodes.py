"""只读 Agent Graph 节点测试。"""

import asyncio
from contextlib import contextmanager

import pytest
from pydantic import Field


def test_load_context_returns_only_initial_message_patch() -> None:
    from app.agent.graph import SYSTEM_PROMPT, load_context

    state = {"run_id": "run-1", "owner_id": 7, "goal": "总结我的 TDD 笔记"}

    patch = load_context(state)

    assert set(patch) == {"messages"}
    assert patch["messages"] == [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {"role": "user", "content": "总结我的 TDD 笔记"},
    ]


def test_load_context_does_not_duplicate_restored_messages() -> None:
    from app.agent.graph import load_context

    state = {
        "run_id": "run-1",
        "owner_id": 7,
        "goal": "goal",
        "messages": [{"role": "user", "content": "already restored"}],
    }

    assert load_context(state) == {}


def test_decide_returns_tool_call_as_json_state_patch() -> None:
    from app.agent.graph import decide
    from app.agent.model_gateway import ModelToolCall, ToolDecision
    from tests.agent.fakes import ScriptedModelGateway

    gateway = ScriptedModelGateway(
        [
            ToolDecision(
                tool_call=ModelToolCall(
                    id="call-1",
                    name="search_notes",
                    arguments={"query": "TDD"},
                )
            )
        ]
    )
    state = {
        "run_id": "run-1",
        "owner_id": 7,
        "goal": "goal",
        "messages": [{"role": "user", "content": "goal"}],
    }

    patch = asyncio.run(decide(state, model_gateway=gateway))

    assert set(patch) == {"messages", "pending_tool_call", "final_answer"}
    assert patch["pending_tool_call"] == {
        "id": "call-1",
        "name": "search_notes",
        "arguments": {"query": "TDD"},
    }
    assert patch["final_answer"] is None
    assert patch["messages"][-1]["role"] == "assistant"


def test_decide_returns_final_answer_as_json_state_patch() -> None:
    from app.agent.graph import decide
    from app.agent.model_gateway import FinalDecision
    from tests.agent.fakes import ScriptedModelGateway

    gateway = ScriptedModelGateway([FinalDecision(final_answer="这是最终答案")])
    state = {
        "run_id": "run-1",
        "owner_id": 7,
        "goal": "goal",
        "messages": [{"role": "user", "content": "goal"}],
    }

    patch = asyncio.run(decide(state, model_gateway=gateway))

    assert patch["pending_tool_call"] is None
    assert patch["final_answer"] == "这是最终答案"
    assert patch["messages"][-1] == {
        "role": "assistant",
        "content": "这是最终答案",
    }


def test_execute_read_uses_short_session_and_observe_appends_result(monkeypatch) -> None:
    from app.agent import graph
    from app.agent.tools.base import ToolInput, ToolOutput, ToolPermission, ToolSpec
    from app.agent.tools.registry import ToolRegistry

    class LookupInput(ToolInput):
        item_id: int = Field(gt=0, strict=True)

    class LookupOutput(ToolOutput):
        title: str

    lifecycle: list[str] = []

    def handler(_session, context, arguments):
        lifecycle.append("invoke")
        assert context.owner_id == 7
        return LookupOutput(title=f"item-{arguments.item_id}")

    registry = ToolRegistry(
        [
            ToolSpec(
                name="lookup",
                description="lookup",
                permission=ToolPermission.READ,
                input_model=LookupInput,
                output_model=LookupOutput,
                handler=handler,
            )
        ]
    )
    registry.freeze()
    monkeypatch.setattr(graph, "READ_TOOL_REGISTRY", registry)

    @contextmanager
    def session_factory():
        lifecycle.append("open")
        try:
            yield object()
        finally:
            lifecycle.append("close")

    state = {
        "run_id": "00000000-0000-0000-0000-000000000001",
        "owner_id": 7,
        "goal": "goal",
        "step_count": 0,
        "messages": [{"role": "user", "content": "goal"}],
        "observations": [],
        "pending_tool_call": {
            "id": "call-1",
            "name": "lookup",
            "arguments": {"item_id": 3},
        },
    }

    execution_patch = graph.execute_read(state, session_factory=session_factory)

    assert lifecycle == ["open", "invoke", "close"]
    assert set(execution_patch) == {"step_count", "observations"}
    assert execution_patch["step_count"] == 1
    assert execution_patch["observations"][-1] == {
        "tool_call_id": "call-1",
        "tool_name": "lookup",
        "ok": True,
        "result": {"title": "item-3"},
    }
    assert all("session" not in key for key in execution_patch)

    observed_state = {**state, **execution_patch}
    observe_patch = graph.observe(observed_state)

    assert observe_patch["pending_tool_call"] is None
    assert observe_patch["messages"][-1]["role"] == "tool"
    assert observe_patch["messages"][-1]["tool_call_id"] == "call-1"


def test_execute_read_turns_unknown_tool_into_observation_and_counts_attempt() -> None:
    from app.agent.graph import execute_read

    opened = False

    @contextmanager
    def session_factory():
        nonlocal opened
        opened = True
        yield object()

    state = {
        "run_id": "00000000-0000-0000-0000-000000000001",
        "owner_id": 7,
        "goal": "goal",
        "step_count": 2,
        "observations": [],
        "pending_tool_call": {
            "id": "call-unknown",
            "name": "unregistered_tool",
            "arguments": {},
        },
    }

    patch = execute_read(state, session_factory=session_factory)

    assert opened is False
    assert patch["step_count"] == 3
    assert patch["observations"][-1] == {
        "tool_call_id": "call-unknown",
        "tool_name": "unregistered_tool",
        "ok": False,
        "error": {"code": "unknown_tool", "message": "工具不存在或未获授权"},
    }


def test_execute_read_turns_validation_error_into_observation_and_closes_session() -> None:
    from app.agent.graph import execute_read

    lifecycle: list[str] = []

    @contextmanager
    def session_factory():
        lifecycle.append("open")
        try:
            yield object()
        finally:
            lifecycle.append("close")

    state = {
        "run_id": "00000000-0000-0000-0000-000000000001",
        "owner_id": 7,
        "goal": "goal",
        "step_count": 0,
        "observations": [],
        "pending_tool_call": {
            "id": "call-invalid",
            "name": "search_notes",
            "arguments": {"limit": 0},
        },
    }

    patch = execute_read(state, session_factory=session_factory)

    assert lifecycle == ["open", "close"]
    assert patch["step_count"] == 1
    assert patch["observations"][-1] == {
        "tool_call_id": "call-invalid",
        "tool_name": "search_notes",
        "ok": False,
        "error": {"code": "invalid_arguments", "message": "工具参数校验失败"},
    }


@pytest.mark.parametrize(
    ("step_count", "max_steps", "expected"),
    [(0, 1, "execute_read"), (1, 1, "finalize"), (2, 3, "execute_read"), (3, 3, "finalize")],
)
def test_route_after_decide_enforces_configurable_budget_boundaries(
    step_count, max_steps, expected
) -> None:
    from app.agent.graph import route_after_decide

    state = {
        "step_count": step_count,
        "pending_tool_call": {"id": "call-1", "name": "search_notes", "arguments": {}},
        "final_answer": None,
    }
    config = {"configurable": {"max_steps": max_steps}}

    assert route_after_decide(state, config) == expected


def test_finalize_marks_budget_exhaustion_without_executing_pending_tool() -> None:
    from app.agent.graph import finalize

    state = {
        "step_count": 1,
        "pending_tool_call": {"id": "call-2", "name": "search_notes", "arguments": {}},
        "final_answer": None,
    }

    patch = finalize(state, {"configurable": {"max_steps": 1}})

    assert patch == {
        "pending_tool_call": None,
        "final_answer": "已达到最大工具调用步数，无法继续执行。",
        "error": {
            "code": "max_steps_exceeded",
            "message": "工具调用步数已达到上限 1",
        },
    }
