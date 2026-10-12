"""Agent 工具的类型契约与服务端调用边界。"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session


class ToolInput(BaseModel):
    """模型可见的工具输入；未知字段一律拒绝。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ToolOutput(BaseModel):
    """工具输出契约，确保进入事件流前可被严格校验。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class ToolPermission(StrEnum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True, slots=True)
class ToolContext:
    """由运行时注入的身份，绝不来自模型参数。"""

    owner_id: int
    run_id: UUID


InputT = TypeVar("InputT", bound=ToolInput)
OutputT = TypeVar("OutputT", bound=ToolOutput)
ToolHandler = Callable[[Session, ToolContext, InputT], OutputT]


@dataclass(frozen=True, slots=True)
class ToolSpec(Generic[InputT, OutputT]):
    name: str
    description: str
    permission: ToolPermission
    input_model: type[InputT]
    output_model: type[OutputT]
    handler: ToolHandler[InputT, OutputT]

    def invoke(
        self,
        session: Session,
        context: ToolContext,
        arguments: InputT | dict[str, object],
    ) -> OutputT:
        """在短生命周期 Session 内校验输入、执行并校验输出。"""

        validated_input = self.input_model.model_validate(arguments)
        result = self.handler(session, context, validated_input)
        return self.output_model.model_validate(result)
