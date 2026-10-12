"""将 OpenAI-compatible 响应收敛为 Agent 内部的单决策协议。"""

import json
from typing import Any, Literal, Protocol, TypeAlias

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, ValidationError

from app.agent.state import JsonObject
from app.settings import Settings


class InvalidModelDecision(ValueError):
    """供应商响应无法表示为唯一且安全的 Agent 决策。"""


class ModelContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ModelToolCall(ModelContract):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments: JsonObject


class ToolDecision(ModelContract):
    kind: Literal["tool"] = "tool"
    tool_call: ModelToolCall


class FinalDecision(ModelContract):
    kind: Literal["final"] = "final"
    final_answer: str = Field(min_length=1)


ModelDecision: TypeAlias = ToolDecision | FinalDecision


class ModelGateway(Protocol):
    async def decide(
        self,
        *,
        messages: list[JsonObject],
        tools: list[dict[str, object]],
    ) -> ModelDecision: ...


_JSON_OBJECT = TypeAdapter(
    dict[str, JsonValue],
    config=ConfigDict(strict=True, allow_inf_nan=False),
)


def parse_model_response(response: object) -> ModelDecision:
    """拒绝模糊响应，保证每轮只能执行一个工具或给出最终答案。"""
    try:
        message = response.choices[0].message  # type: ignore[attr-defined]
        tool_calls = list(message.tool_calls or [])
        content = message.content.strip() if isinstance(message.content, str) else ""
    except (AttributeError, IndexError, TypeError) as exc:
        raise InvalidModelDecision("model response is missing a decision") from exc

    if len(tool_calls) == 1 and not content:
        call = tool_calls[0]
        try:
            decoded = json.loads(call.function.arguments)
            arguments = _JSON_OBJECT.validate_python(decoded)
            return ToolDecision(
                tool_call=ModelToolCall(
                    id=call.id,
                    name=call.function.name,
                    arguments=arguments,
                )
            )
        except (AttributeError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise InvalidModelDecision("tool call is invalid") from exc

    if not tool_calls and content:
        return FinalDecision(final_answer=content)

    raise InvalidModelDecision("model must return exactly one tool call or final answer")


class OpenAICompatibleModelGateway:
    """OpenAI-compatible 适配器；只保留已构造客户端，不保存或暴露密钥。"""

    def __init__(self, *, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenAICompatibleModelGateway":
        client = AsyncOpenAI(
            api_key=settings.agent_model_api_key,
            base_url=settings.agent_model_base_url,
            timeout=settings.agent_run_timeout_seconds,
        )
        return cls(client=client, model=settings.agent_model_name)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(model={self._model!r})"

    async def decide(
        self,
        *,
        messages: list[JsonObject],
        tools: list[dict[str, object]],
    ) -> ModelDecision:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            parallel_tool_calls=False,
        )
        decision = parse_model_response(response)
        if isinstance(decision, ToolDecision):
            # 工具输出/笔记可包含任意文字，但不能扩展服务端本轮公布的工具白名单。
            allowed_names = {tool["function"]["name"] for tool in tools}
            if decision.tool_call.name not in allowed_names:
                raise InvalidModelDecision("model selected a tool not allowed by server")
        return decision
