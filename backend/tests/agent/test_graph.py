"""只读 Agent Graph 的完整路径测试。"""

import asyncio
from contextlib import contextmanager

import pytest

from app.agent.model_gateway import FinalDecision, ModelToolCall, ToolDecision
from tests.agent.fakes import ScriptedModelGateway


@pytest.fixture(autouse=True)
def isolate_graph_routing_from_persistent_cancel_check(monkeypatch):
    # 本文件只验证 Graph 路由；取消门禁由 test_cancel 使用真实 Run 表验证。
    from app.agent import graph

    monkeypatch.setattr(graph, "ensure_run_not_cancelled", lambda state, *, session_factory: None)


def _initial_state():
    return {
        "run_id": "00000000-0000-0000-0000-000000000001",
        "owner_id": 7,
        "goal": "查找 TDD 笔记",
        "step_count": 0,
        "plan": [],
        "messages": [],
        "pending_tool_call": None,
        "observations": [],
        "final_answer": None,
        "error": None,
    }


def test_compiled_graph_takes_final_branch_without_opening_database() -> None:
    from app.agent.graph import compile_read_graph

    gateway = ScriptedModelGateway([FinalDecision(final_answer="无需工具")])

    @contextmanager
    def forbidden_session_factory():
        raise AssertionError("final branch must not open a database session")
        yield

    graph = compile_read_graph(
        model_gateway=gateway,
        session_factory=forbidden_session_factory,
    )
    result = asyncio.run(
        graph.ainvoke(
            _initial_state(),
            config={"configurable": {"max_steps": 1}},
        )
    )

    assert result["final_answer"] == "无需工具"
    assert result["step_count"] == 0
    assert gateway.call_count == 1


def test_compiled_graph_runs_tool_observes_and_then_finalizes(monkeypatch) -> None:
    from app.agent import graph as graph_module
    from app.agent.graph import compile_read_graph
    from app.agent.tools.base import ToolInput, ToolOutput, ToolPermission, ToolSpec
    from app.agent.tools.registry import ToolRegistry

    class LookupInput(ToolInput):
        query: str

    class LookupOutput(ToolOutput):
        count: int

    registry = ToolRegistry(
        [
            ToolSpec(
                name="lookup",
                description="lookup",
                permission=ToolPermission.READ,
                input_model=LookupInput,
                output_model=LookupOutput,
                handler=lambda _session, _context, _arguments: LookupOutput(count=2),
            )
        ]
    )
    registry.freeze()
    monkeypatch.setattr(graph_module, "READ_TOOL_REGISTRY", registry)
    gateway = ScriptedModelGateway(
        [
            ToolDecision(
                tool_call=ModelToolCall(
                    id="call-1",
                    name="lookup",
                    arguments={"query": "TDD"},
                )
            ),
            FinalDecision(final_answer="找到 2 条"),
        ]
    )

    @contextmanager
    def session_factory():
        yield object()

    graph = compile_read_graph(
        model_gateway=gateway,
        session_factory=session_factory,
    )
    result = asyncio.run(
        graph.ainvoke(
            _initial_state(),
            config={"configurable": {"max_steps": 3}},
        )
    )

    assert result["final_answer"] == "找到 2 条"
    assert result["step_count"] == 1
    assert result["observations"] == [
        {
            "tool_call_id": "call-1",
            "tool_name": "lookup",
            "ok": True,
            "result": {"count": 2},
        }
    ]
    assert gateway.call_count == 2


def _install_counting_tool(monkeypatch):
    from app.agent import graph as graph_module
    from app.agent.tools.base import ToolInput, ToolOutput, ToolPermission, ToolSpec
    from app.agent.tools.registry import ToolRegistry

    class CountingInput(ToolInput):
        value: int

    class CountingOutput(ToolOutput):
        value: int

    executed: list[int] = []

    def handler(_session, _context, arguments):
        executed.append(arguments.value)
        return CountingOutput(value=arguments.value)

    registry = ToolRegistry(
        [
            ToolSpec(
                name="counting_tool",
                description="count calls",
                permission=ToolPermission.READ,
                input_model=CountingInput,
                output_model=CountingOutput,
                handler=handler,
            )
        ]
    )
    registry.freeze()
    monkeypatch.setattr(graph_module, "READ_TOOL_REGISTRY", registry)
    return executed


@pytest.mark.parametrize("max_steps", [1, 3])
def test_compiled_graph_allows_final_answer_after_nth_tool_observation(
    monkeypatch, max_steps
) -> None:
    from app.agent.graph import compile_read_graph

    executed = _install_counting_tool(monkeypatch)
    tool_decisions = [
        ToolDecision(
            tool_call=ModelToolCall(
                id=f"call-{step}",
                name="counting_tool",
                arguments={"value": step},
            )
        )
        for step in range(1, max_steps + 1)
    ]
    gateway = ScriptedModelGateway(
        [*tool_decisions, FinalDecision(final_answer="budget used, final returned")]
    )

    @contextmanager
    def session_factory():
        yield object()

    graph = compile_read_graph(
        model_gateway=gateway,
        session_factory=session_factory,
    )
    result = asyncio.run(
        graph.ainvoke(
            _initial_state(),
            config={"configurable": {"max_steps": max_steps}},
        )
    )

    assert executed == list(range(1, max_steps + 1))
    assert result["step_count"] == max_steps
    assert len(result["observations"]) == max_steps
    assert result["final_answer"] == "budget used, final returned"
    assert result["error"] is None
    assert gateway.call_count == max_steps + 1


def test_compiled_graph_never_executes_tool_n_plus_one_when_model_continues(
    monkeypatch,
) -> None:
    from app.agent.graph import compile_read_graph

    max_steps = 3
    executed = _install_counting_tool(monkeypatch)
    gateway = ScriptedModelGateway(
        [
            ToolDecision(
                tool_call=ModelToolCall(
                    id=f"call-{step}",
                    name="counting_tool",
                    arguments={"value": step},
                )
            )
            for step in range(1, max_steps + 2)
        ]
    )

    @contextmanager
    def session_factory():
        yield object()

    graph = compile_read_graph(
        model_gateway=gateway,
        session_factory=session_factory,
    )
    result = asyncio.run(
        graph.ainvoke(
            _initial_state(),
            config={"configurable": {"max_steps": max_steps}},
        )
    )

    assert executed == [1, 2, 3]
    assert result["step_count"] == max_steps
    assert len(result["observations"]) == max_steps
    assert result["final_answer"] == "已达到最大工具调用步数，无法继续执行。"
    assert result["error"]["code"] == "max_steps_exceeded"
    assert gateway.call_count == max_steps + 1
