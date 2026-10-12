from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.agent.schemas import (
    ApprovalDecision,
    ApprovalDecisionType,
    RunCreate,
    RunDetail,
    RunStatus,
    RunSummary,
)


def _summary_payload() -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "goal": "整理本周任务",
        "status": "queued",
        "created_at": "2026-09-20T08:00:00Z",
        "updated_at": "2026-09-20T08:01:00Z",
    }


def _detail_payload() -> dict[str, object]:
    return {
        **_summary_payload(),
        "thread_id": str(uuid4()),
        "graph_version": "v1",
        "max_steps": 12,
        "timeout_seconds": 300,
        "step_count": 2,
        "final_answer": None,
        "error_code": None,
        "error_message": None,
        "started_at": "2026-09-20T08:00:01Z",
        "finished_at": None,
    }


class TestRunSchemas:
    def test_run_contract_normalizes_input_and_preserves_domain_types(self):
        create = RunCreate.model_validate({"goal": "  整理本周任务  "})
        summary = RunSummary.model_validate(_summary_payload())
        detail = RunDetail.model_validate(_detail_payload())

        assert create.goal == "整理本周任务"
        assert {status.value for status in RunStatus} == {
            "queued",
            "running",
            "waiting_approval",
            "completed",
            "failed",
            "cancelling",
            "interrupted",
            "cancelled",
        }
        assert isinstance(summary.id, UUID)
        assert isinstance(summary.created_at, datetime)
        assert isinstance(summary.updated_at, datetime)
        assert isinstance(detail.thread_id, UUID)
        assert isinstance(detail.started_at, datetime)

    @pytest.mark.parametrize("goal", ["", "   ", "x" * 4001])
    def test_run_create_rejects_invalid_goal(self, goal):
        with pytest.raises(ValidationError):
            RunCreate.model_validate({"goal": goal})

    def test_run_models_reject_unknown_status_invalid_identifiers_and_extra_fields(self):
        invalid_summary = {**_summary_payload(), "status": "unknown"}
        invalid_detail = {**_detail_payload(), "thread_id": "not-a-uuid"}

        with pytest.raises(ValidationError):
            RunSummary.model_validate(invalid_summary)
        with pytest.raises(ValidationError):
            RunDetail.model_validate(invalid_detail)

        valid_payloads = [
            (RunCreate, {"goal": "整理任务"}),
            (RunSummary, _summary_payload()),
            (RunDetail, _detail_payload()),
        ]
        for model, payload in valid_payloads:
            with pytest.raises(ValidationError):
                model.model_validate({**payload, "unexpected": True})


class TestApprovalDecision:
    @pytest.mark.parametrize(
        ("decision", "edited_arguments"),
        [
            ("approve", None),
            ("reject", None),
            ("edit", {"priority": "high"}),
        ],
    )
    def test_approval_decision_accepts_valid_decision_shape(self, decision, edited_arguments):
        approval = ApprovalDecision.model_validate(
            {
                "decision": decision,
                "revision": 1,
                "edited_arguments": edited_arguments,
            }
        )

        assert approval.decision.value == decision
        assert approval.edited_arguments == edited_arguments
        assert {item.value for item in ApprovalDecisionType} == {"approve", "reject", "edit"}

    @pytest.mark.parametrize(
        "payload",
        [
            {"decision": "edit", "revision": 1, "edited_arguments": None},
            {"decision": "approve", "revision": 1, "edited_arguments": {}},
            {"decision": "reject", "revision": 1, "edited_arguments": {}},
            {"decision": "approve", "revision": 0, "edited_arguments": None},
            {"decision": "unknown", "revision": 1, "edited_arguments": None},
            {
                "decision": "edit",
                "revision": 1,
                "edited_arguments": {"value": float("nan")},
            },
            {
                "decision": "edit",
                "revision": 1,
                "edited_arguments": {"value": float("inf")},
            },
            {
                "decision": "approve",
                "revision": 1,
                "edited_arguments": None,
                "unexpected": True,
            },
        ],
    )
    def test_approval_decision_rejects_invalid_decision_shape(self, payload):
        with pytest.raises(ValidationError):
            ApprovalDecision.model_validate(payload)
