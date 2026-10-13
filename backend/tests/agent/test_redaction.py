"""公开事件不可带出工具结果中的固定敏感字段。"""

from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agent.event_recorder import map_graph_output, redact_public_value
from app.agent.repository import append_event
from app.agent_models import AgentRun
from app.config import Base
from app.models import User


def test_graph_events_redact_nested_sensitive_key_and_authorization_fields() -> None:
    drafts = map_graph_output(
        {
            "observations": [
                {
                    "tool_call_id": "call-1",
                    "tool_name": "search_notes",
                    "ok": True,
                    "result": {
                        "items": [
                            {
                                "title": "integration",
                                "api_key": "sk-private",
                                "headers": {"Authorization": "Bearer private-token"},
                            }
                        ]
                    },
                }
            ],
            "final_answer": "完成",
            "step_count": 1,
        }
    )

    assert drafts[0].data["result"] == {
        "items": [
            {
                "title": "integration",
                "api_key": "[REDACTED]",
                "headers": {"Authorization": "[REDACTED]"},
            }
        ]
    }


def test_graph_events_redact_authorization_and_api_key_in_free_text() -> None:
    drafts = map_graph_output(
        {
            "observations": [
                {
                    "tool_call_id": "call-1",
                    "tool_name": "search_notes",
                    "ok": False,
                    "error": {
                        "code": "upstream_error",
                        "message": "Authorization: Bearer nested-token; API_KEY=sk-nested",
                    },
                }
            ],
            "error": {
                "code": "model_error",
                "message": "Authorization: Bearer public-token; API_KEY=sk-public",
            },
        }
    )

    public_event_data = str([draft.data for draft in drafts])
    for secret in ("nested-token", "sk-nested", "public-token", "sk-public"):
        assert secret not in public_event_data
    assert public_event_data.count("[REDACTED]") == 4


def test_graph_events_redact_common_credential_header_variants() -> None:
    drafts = map_graph_output(
        {
            "observations": [
                {
                    "tool_call_id": "call-1",
                    "tool_name": "get_note",
                    "ok": True,
                    "result": {
                        "X-API-Key": "header-secret",
                        "Proxy-Authorization": "Basic auth-secret",
                        "OPENAI_API_KEY": "provider-secret",
                        "client_secret": "oauth-secret",
                    },
                }
            ],
            "final_answer": "完成",
        }
    )

    assert drafts[0].data["result"] == {
        "X-API-Key": "[REDACTED]",
        "Proxy-Authorization": "[REDACTED]",
        "OPENAI_API_KEY": "[REDACTED]",
        "client_secret": "[REDACTED]",
    }


def test_repository_redacts_events_from_all_call_sites() -> None:
    """审批和写工具直接调用仓储，仍必须经过统一公开事件边界。"""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    run_id = str(uuid4())
    with Session(engine) as session:
        owner = User(username="redaction-owner", password_hash="hash")
        session.add(owner)
        session.flush()
        session.add(AgentRun(
            id=run_id, owner_id=owner.id, goal="测试", thread_id=run_id,
            graph_version="read-v1", max_steps=2, timeout_seconds=60,
        ))
        session.flush()
        event = append_event(
            session,
            run_id=run_id,
            event_type="tool.completed",
            payload_json={"result": {"api_key": "sk-direct", "message": "Authorization: Bearer direct-token"}},
        )
        assert "sk-direct" not in str(event.payload_json)
        assert "direct-token" not in str(event.payload_json)
    engine.dispose()


def test_json_formatted_credentials_are_redacted_from_final_answer() -> None:
    answer = '{"Authorization":"Bearer json-token","api_key":"sk-json"}'
    public_answer = redact_public_value(answer)
    event = map_graph_output({"final_answer": answer})[-1]

    for secret in ("json-token", "sk-json"):
        assert secret not in public_answer
        assert secret not in str(event.data)


def test_graph_events_redact_provider_prefixed_key_in_error_text() -> None:
    drafts = map_graph_output(
        {
            "error": {
                "code": "provider_error",
                "message": "OPENAI_API_KEY=provider-token is invalid",
            }
        }
    )

    assert drafts[0].data["message"] == "OPENAI_API_KEY= [REDACTED] is invalid"
