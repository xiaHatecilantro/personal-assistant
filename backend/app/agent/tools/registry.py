"""工具白名单注册表；未注册的能力对模型不可见也不可调用。"""

from collections.abc import Collection, Iterable
from typing import Any

from app.agent.tools.base import ToolPermission, ToolSpec


class DuplicateToolNameError(ValueError):
    pass


class FrozenToolRegistryError(RuntimeError):
    pass


class ToolPermissionError(ValueError):
    pass


class ToolRegistry:
    def __init__(
        self,
        specs: Iterable[ToolSpec[Any, Any]] = (),
        *,
        allowed_permissions: Collection[ToolPermission] | None = None,
    ) -> None:
        self._specs: dict[str, ToolSpec[Any, Any]] = {}
        self._allowed_permissions = (
            frozenset(allowed_permissions) if allowed_permissions is not None else None
        )
        self._is_frozen = False
        for spec in specs:
            self.register(spec)

    def register(self, spec: ToolSpec[Any, Any]) -> None:
        if self._is_frozen:
            raise FrozenToolRegistryError("tool registry is frozen")
        if (
            self._allowed_permissions is not None
            and spec.permission not in self._allowed_permissions
        ):
            raise ToolPermissionError(f"tool permission is not allowed: {spec.permission}")
        if spec.name in self._specs:
            raise DuplicateToolNameError(f"tool already registered: {spec.name}")
        self._specs[spec.name] = spec

    @property
    def is_frozen(self) -> bool:
        return self._is_frozen

    def freeze(self) -> None:
        self._is_frozen = True

    def get(self, name: str) -> ToolSpec[Any, Any]:
        return self._specs[name]

    def names(self) -> tuple[str, ...]:
        return tuple(self._specs)

    def model_schemas(self) -> list[dict[str, object]]:
        """返回 OpenAI-compatible tools schema，不包含服务端身份和执行对象。"""

        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.input_model.model_json_schema(),
                },
            }
            for spec in self._specs.values()
        ]
