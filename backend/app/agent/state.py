"""LangGraph 节点之间共享的最小 JSON 状态结构。

状态保持纯 JSON 可序列化，才能安全写入 Checkpointer，并在进程重启后恢复执行。
"""

from typing import TypeAlias, TypedDict


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class AgentState(TypedDict, total=False):
    run_id: str
    owner_id: int
    goal: str
    step_count: int
    plan: list[str]
    messages: list[JsonObject]
    pending_tool_call: JsonObject | None
    observations: list[JsonObject]
    final_answer: str | None
    error: JsonObject | None
