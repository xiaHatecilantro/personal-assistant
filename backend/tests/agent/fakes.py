"""Agent Graph 测试替身；所有响应由内存脚本提供，绝不访问网络。"""

from collections.abc import Iterable

from app.agent.model_gateway import ModelDecision
from app.agent.state import JsonObject


class ScriptedModelGateway:
    def __init__(self, decisions: Iterable[ModelDecision]) -> None:
        self._decisions = [decision.model_copy(deep=True) for decision in decisions]
        self.call_count = 0

    async def decide(
        self,
        *,
        messages: list[JsonObject],
        tools: list[dict[str, object]],
    ) -> ModelDecision:
        del messages, tools
        if self.call_count >= len(self._decisions):
            raise AssertionError("script exhausted")
        decision = self._decisions[self.call_count].model_copy(deep=True)
        self.call_count += 1
        return decision
