import json
from typing import get_type_hints

from app.agent.state import AgentState


def test_agent_state_round_trips_through_json():
    state: AgentState = {
        "run_id": "run-123",
        "owner_id": 42,
        "goal": "整理本周任务并给出执行顺序",
        "step_count": 1,
        "plan": ["读取任务", "按优先级排序"],
        "messages": [
            {"role": "user", "content": "帮我规划本周任务"},
            {"role": "assistant", "content": "我先读取任务列表"},
        ],
        "pending_tool_call": {
            "name": "list_tasks",
            "arguments": {"status": "todo"},
        },
        "observations": [
            {"tool": "list_tasks", "result": {"count": 3}},
        ],
        "final_answer": None,
        "error": None,
    }

    restored = json.loads(json.dumps(state, ensure_ascii=False))

    assert restored == state


def test_agent_state_annotations_only_describe_persistable_business_data():
    annotations = get_type_hints(AgentState)
    expected_fields = {
        "run_id",
        "owner_id",
        "goal",
        "step_count",
        "plan",
        "messages",
        "pending_tool_call",
        "observations",
        "final_answer",
        "error",
    }
    forbidden_terms = {
        "session",
        "client",
        "checkpointer",
        "api_key",
        "token",
        "secret",
    }

    assert set(annotations) == expected_fields

    annotation_text = " ".join(
        [*(name.lower() for name in annotations), *(repr(value).lower() for value in annotations.values())]
    )
    assert all(term not in annotation_text for term in forbidden_terms)
