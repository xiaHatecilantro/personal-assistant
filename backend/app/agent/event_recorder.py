"""把 Graph 状态投影为版本稳定、可 JSON 回放的应用事件。"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ConfigDict, JsonValue, TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.events import EventType
from app.agent.repository import append_event
from app.agent_models import AgentEvent


_JSON_OBJECT = TypeAdapter(
    dict[str, JsonValue],
    config=ConfigDict(strict=True, allow_inf_nan=False),
)
_STRING_LIST = TypeAdapter(
    list[str],
    config=ConfigDict(strict=True),
)
_SENSITIVE_FIELDS = frozenset(
    {
        "api_key", "apikey", "authorization", "access_token", "refresh_token",
        "password", "secret", "token", "client_secret",
    }
)
_SENSITIVE_SUFFIXES = ("_api_key", "_authorization", "_token", "_secret")
_CREDENTIAL_TEXT = re.compile(
    r"\b((?:proxy[-_])?authorization|(?:[a-z0-9]+[-_])*api[-_]?key|"
    r"access[-_]?token|refresh[-_]?token|"
    r"client[-_]?secret|password)(?:[\"'])?\s*([:=])\s*(?:(?:Bearer|Basic)\s+)?"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;}\]]+)",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class EventDraft:
    """尚未分配数据库 sequence/created_at 的稳定事件内容。"""

    type: EventType
    data: dict[str, JsonValue]


def map_graph_output(output: Mapping[str, Any]) -> tuple[EventDraft, ...]:
    """仅选择公开字段；messages、metadata 等 LangGraph 内部值一律不透传。"""
    drafts: list[EventDraft] = []
    plan = output.get("plan")
    if plan:
        drafts.append(
            EventDraft(
                type=EventType.PLAN_UPDATED,
                data={"items": _STRING_LIST.validate_python(plan)},
            )
        )

    for raw_observation in output.get("observations", []):
        observation = _JSON_OBJECT.validate_python(raw_observation)
        common: dict[str, JsonValue] = {
            "tool_call_id": _required_text(observation, "tool_call_id"),
            "tool_name": _required_text(observation, "tool_name"),
        }
        if observation.get("ok") is True:
            common["result"] = observation.get("result")
            drafts.append(EventDraft(type=EventType.TOOL_COMPLETED, data=common))
        else:
            common["error"] = observation.get("error")
            drafts.append(EventDraft(type=EventType.TOOL_FAILED, data=common))

    error = output.get("error")
    if error is not None:
        public_error = _JSON_OBJECT.validate_python(error)
        drafts.append(
            EventDraft(
                type=EventType.RUN_FAILED,
                data={
                    "error_code": _required_text(public_error, "code"),
                    "message": _required_text(public_error, "message"),
                },
            )
        )
    else:
        terminal = _JSON_OBJECT.validate_python(
            {
                "final_answer": output.get("final_answer"),
                "step_count": output.get("step_count", 0),
            }
        )
        drafts.append(EventDraft(type=EventType.RUN_COMPLETED, data=terminal))
    return tuple(
        EventDraft(type=draft.type, data=redact_public_value(draft.data)) for draft in drafts
    )


def record_graph_output(
    session: Session,
    *,
    run_id: str,
    output: Mapping[str, Any],
) -> list[AgentEvent]:
    """在调用方事务中追加事件；工具事务已发出的结果不可重复投影。"""
    existing_tool_calls = {
        event.payload_json.get("tool_call_id")
        for event in session.scalars(
            select(AgentEvent).where(
                AgentEvent.run_id == run_id,
                AgentEvent.event_type.in_(("tool.completed", "tool.failed")),
            )
        )
    }
    events: list[AgentEvent] = []
    for draft in map_graph_output(output):
        if draft.type in (EventType.TOOL_COMPLETED, EventType.TOOL_FAILED):
            tool_call_id = draft.data["tool_call_id"]
            if tool_call_id in existing_tool_calls:
                continue
            existing_tool_calls.add(tool_call_id)
        events.append(append_event(
            session,
            run_id=run_id,
            event_type=draft.type.value,
            payload_json=draft.data,
        ))
    return events


def _required_text(data: Mapping[str, JsonValue], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def redact_public_value(value: JsonValue) -> JsonValue:
    """脱敏公开 JSON 副本；保留内部 Graph/工具结果供后续推理。"""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if _is_sensitive_field(key)
            else redact_public_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_public_value(item) for item in value]
    if isinstance(value, str):
        return _CREDENTIAL_TEXT.sub(
            lambda match: f"{match.group(1)}{match.group(2)} [REDACTED]", value
        )
    return value


def _is_sensitive_field(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return normalized in _SENSITIVE_FIELDS or normalized.endswith(_SENSITIVE_SUFFIXES)
