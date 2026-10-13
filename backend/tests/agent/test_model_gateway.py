"""模型网关契约测试：将供应商响应收敛为单工具调用或最终回答。"""

import asyncio
from types import SimpleNamespace

import pytest


def _response(*, content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _tool_call(*, call_id="call-1", name="search_notes", arguments='{"query":"TDD"}'):
    function = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(id=call_id, function=function)


def test_parse_model_response_accepts_exactly_one_tool_call() -> None:
    from app.agent.model_gateway import ToolDecision, parse_model_response

    decision = parse_model_response(_response(tool_calls=[_tool_call()]))

    assert isinstance(decision, ToolDecision)
    assert decision.tool_call.model_dump() == {
        "id": "call-1",
        "name": "search_notes",
        "arguments": {"query": "TDD"},
    }


def test_parse_model_response_accepts_final_answer() -> None:
    from app.agent.model_gateway import FinalDecision, parse_model_response

    decision = parse_model_response(_response(content="最终答案"))

    assert isinstance(decision, FinalDecision)
    assert decision.final_answer == "最终答案"


@pytest.mark.parametrize(
    "response",
    [
        _response(),
        _response(content="answer", tool_calls=[_tool_call()]),
        _response(tool_calls=[_tool_call(), _tool_call(call_id="call-2")]),
    ],
)
def test_parse_model_response_rejects_ambiguous_decision(response) -> None:
    from app.agent.model_gateway import InvalidModelDecision, parse_model_response

    with pytest.raises(InvalidModelDecision):
        parse_model_response(response)


def test_parse_model_response_rejects_non_object_arguments() -> None:
    from app.agent.model_gateway import InvalidModelDecision, parse_model_response

    with pytest.raises(InvalidModelDecision):
        parse_model_response(_response(tool_calls=[_tool_call(arguments="[]")]))


def test_openai_gateway_uses_only_server_settings_and_disables_parallel_calls(
    monkeypatch,
) -> None:
    from app.agent import model_gateway

    captured: dict[str, object] = {}
    response = _response(content="done")

    class FakeCompletions:
        async def create(self, **kwargs):
            captured["request"] = kwargs
            return response

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    settings = SimpleNamespace(
        agent_model_api_key="server-secret",
        agent_model_base_url="https://model.internal/v1",
        agent_model_name="test-model",
        agent_run_timeout_seconds=17,
    )
    monkeypatch.setattr(model_gateway, "AsyncOpenAI", FakeAsyncOpenAI, raising=False)

    gateway = model_gateway.OpenAICompatibleModelGateway.from_settings(settings)
    decision = asyncio.run(
        gateway.decide(
            messages=[{"role": "user", "content": "goal"}],
            tools=[{"type": "function", "function": {"name": "search_notes"}}],
        )
    )

    assert decision.final_answer == "done"
    assert captured["client"] == {
        "api_key": "server-secret",
        "base_url": "https://model.internal/v1",
        "timeout": 17,
    }
    assert captured["request"] == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "goal"}],
        "tools": [{"type": "function", "function": {"name": "search_notes"}}],
        "tool_choice": "auto",
        "parallel_tool_calls": False,
    }


def test_openai_gateway_repr_never_contains_api_key(monkeypatch) -> None:
    from app.agent import model_gateway

    class FakeAsyncOpenAI:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=object())

    secret = "server-secret-must-not-leak"
    settings = SimpleNamespace(
        agent_model_api_key=secret,
        agent_model_base_url="https://model.internal/v1",
        agent_model_name="test-model",
        agent_run_timeout_seconds=17,
    )
    monkeypatch.setattr(model_gateway, "AsyncOpenAI", FakeAsyncOpenAI, raising=False)

    gateway = model_gateway.OpenAICompatibleModelGateway.from_settings(settings)

    assert secret not in repr(gateway)


def test_scripted_model_replays_decisions_in_order_without_network() -> None:
    from app.agent.model_gateway import FinalDecision, ModelToolCall, ToolDecision
    from tests.agent.fakes import ScriptedModelGateway

    script = [
        ToolDecision(
            tool_call=ModelToolCall(
                id="call-1",
                name="search_notes",
                arguments={"query": "TDD"},
            )
        ),
        FinalDecision(final_answer="done"),
    ]
    gateway = ScriptedModelGateway(script)

    first = asyncio.run(gateway.decide(messages=[], tools=[]))
    second = asyncio.run(gateway.decide(messages=[], tools=[]))

    assert first == script[0]
    assert second == script[1]
    assert gateway.call_count == 2


def test_scripted_model_fails_explicitly_when_script_is_exhausted() -> None:
    from app.agent.model_gateway import FinalDecision
    from tests.agent.fakes import ScriptedModelGateway

    gateway = ScriptedModelGateway([FinalDecision(final_answer="done")])
    asyncio.run(gateway.decide(messages=[], tools=[]))

    with pytest.raises(AssertionError, match="script exhausted"):
        asyncio.run(gateway.decide(messages=[], tools=[]))
