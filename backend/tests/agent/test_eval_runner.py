"""Fake 只替代模型，评测证据必须来自真实 Graph、数据库和审批边界。"""

import pytest
from sqlalchemy import select

from evals.runner import EvalAssertion, load_cases, run_case, run_suite
from app.models import Note, Task
from tests.agent.asyncio_utils import run_async


pytestmark = pytest.mark.evaluation


def test_runner_collects_real_read_tool_observation_and_runtime_events():
    result = run_async(run_case(load_cases()[0], seed=42))
    assert result.passed, result.failure_reasons
    assert result.tool_names == ["list_tasks"]
    assert result.status == "completed"
    assert result.step_count == 1
    assert [event["type"] for event in result.events] == [
        "run.started", "tool.completed", "run.completed",
    ]
    assert result.events[1]["data"]["result"]["count"] == 2


def test_runner_approved_write_creates_a_real_task_and_execution_ledger():
    case = next(case for case in load_cases() if case.id == "write-task-approved")
    result = run_async(run_case(case))
    assert result.passed, result.failure_reasons
    assert result.status == "completed"
    assert any(event["type"] == "approval.resolved" for event in result.events)


def test_runner_detects_repeat_approval_conflict_without_duplicate_business_write():
    case = next(case for case in load_cases() if case.id == "write-repeat-decision")
    result = run_async(run_case(case))
    assert result.passed, result.failure_reasons
    assert result.write_checks == 1


def test_runner_replays_approved_tool_against_real_ledger_without_duplicate_rows():
    case = next(case for case in load_cases() if case.id == "write-idempotent-replay")
    result = run_async(run_case(case))
    assert result.passed, result.failure_reasons
    assert result.idempotency_checks == result.idempotency_passes == 1


def test_runner_probes_cross_user_run_event_approval_cancel_and_resume_apis():
    case = next(case for case in load_cases() if case.id == "permission-api-isolation")
    result = run_async(run_case(case))
    assert result.passed, result.failure_reasons
    assert result.authorization_checks == result.authorization_blocks == 7
    assert result.unauthorized_writes == 0


def test_runner_cancels_waiting_approval_without_executing_proposed_write():
    case = next(case for case in load_cases() if case.id == "recovery-cancel-waiting")
    result = run_async(run_case(case))
    assert result.passed, result.failure_reasons
    assert result.status == "cancelled"
    assert result.tool_names == []


def test_runner_cancels_a_real_runtime_task_while_model_decision_is_in_flight():
    case = next(case for case in load_cases() if case.id == "recovery-cancel-running")
    result = run_async(run_case(case))
    assert result.passed, result.failure_reasons
    assert result.status == "cancelled"
    assert result.step_count == 0


def test_runner_rebuilds_runtime_and_graph_before_resuming_original_approval_checkpoint():
    case = next(case for case in load_cases() if case.id == "recovery-new-runtime-waiting")
    result = run_async(run_case(case))
    assert result.passed, result.failure_reasons
    assert result.runtime_instances == 2
    assert result.write_checks == 1


def test_runner_recovers_after_approval_commit_before_background_resume_dispatch():
    case = next(case for case in load_cases() if case.id == "recovery-decision-committed")
    result = run_async(run_case(case))
    assert result.passed, result.failure_reasons
    assert result.runtime_instances == 2
    assert any(event["type"] == "run.interrupted" for event in result.events)


def test_all_thirty_scripted_cases_validate_actual_tool_results_and_database_effects():
    results = run_async(run_suite(seed=42))
    assert len(results) == 30
    assert all(result.passed for result in results), {
        result.case_id: result.failure_reasons for result in results if not result.passed
    }


def test_idempotency_evidence_fails_when_replay_returns_same_result_but_writes_an_extra_row(monkeypatch):
    from evals import runner

    original = runner.execute_approved_write

    def duplicate_write(session, context, call_id, tool_name):
        result = original(session, context, call_id, tool_name)
        session.add(Task(owner_id=context.owner_id, title="重复副作用"))
        session.flush()
        assert len(session.scalars(select(Task)).all()) == 5
        return result

    monkeypatch.setattr(runner, "execute_approved_write", duplicate_write)
    case = next(case for case in load_cases() if case.id == "write-idempotent-replay")
    result = run_async(run_case(case))
    assert result.idempotency_passes == 0
    assert result.unauthorized_writes == 1
    assert not result.passed


def test_authorization_metrics_count_real_foreign_tool_lookup_and_block_result():
    case = next(case for case in load_cases() if case.id == "permission-foreign-task")
    result = run_async(run_case(case))
    assert result.authorization_checks == result.authorization_blocks == 1


def test_same_seed_repeats_the_same_results_and_normalized_real_approval_events():
    case = next(case for case in load_cases() if case.id == "write-task-approved")
    first = run_async(run_case(case, seed=42))
    second = run_async(run_case(case, seed=42))
    assert first.model_dump(exclude={"duration_ms"}) == second.model_dump(exclude={"duration_ms"})


def test_failed_case_explains_actual_value_instead_of_copying_the_expected_value():
    case = load_cases()[0].model_copy(update={
        "assertions": [EvalAssertion(path="task_count", value=99)],
    })
    result = run_async(run_case(case))
    assert not result.passed
    assert result.failure_reasons == ["task_count: expected equal 99, observed 2"]


@pytest.mark.parametrize("case_id,executor,entity", [
    ("permission-foreign-task", "execute_read", "task"),
    ("permission-foreign-note", "execute_read", "note"),
    ("permission-foreign-write", "execute_write", "task"),
])
def test_foreign_lookup_found_false_does_not_count_as_blocked_when_private_payload_leaks(
    monkeypatch, case_id, executor, entity,
):
    from app.agent import graph

    original = getattr(graph, executor)

    def leaking_read(state, *, session_factory):
        patch = original(state, session_factory=session_factory)
        observation = patch["observations"][-1]
        observation.setdefault("result", {})[entity] = {"title": "其他用户私密内容"}
        return patch

    monkeypatch.setattr(graph, executor, leaking_read)
    case = next(case for case in load_cases() if case.id == case_id)
    result = run_async(run_case(case))
    assert result.authorization_checks == 1
    assert result.authorization_blocks == 0
    assert not result.passed
    assert any("authorization" in reason for reason in result.failure_reasons)


def test_approved_update_cannot_hide_extra_unapproved_field_changes_on_the_same_entity(monkeypatch):
    from app.agent.tools import tasks

    original = tasks._update_task

    def extra_update(session, context, arguments):
        result = original(session, context, arguments)
        session.get(Task, arguments["task_id"]).title = "未批准的标题修改"
        session.flush()
        return result

    monkeypatch.setattr(tasks, "_update_task", extra_update)
    case = next(case for case in load_cases() if case.id == "write-task-update")
    result = run_async(run_case(case))
    assert result.unauthorized_writes > 0
    assert not result.passed
    assert any("unauthorized writes" in reason for reason in result.failure_reasons)


@pytest.mark.parametrize("case_id,tool_name", [
    ("write-task-approved", "create_task"),
    ("write-note-approved", "create_note"),
])
def test_approved_creation_also_checks_default_and_server_derived_entity_fields(
    monkeypatch, case_id, tool_name,
):
    from app.agent.tools import notes, tasks

    module = tasks if tool_name == "create_task" else notes
    handler = "_create_task" if tool_name == "create_task" else "create_approved_note"
    original = getattr(module, handler)

    def corrupted_create(session, context, arguments):
        result = original(session, context, arguments)
        if tool_name == "create_task":
            session.get(Task, result["task_id"]).status = "done"
        else:
            session.get(Note, result["note_id"]).wikilinks = '["未批准的派生字段"]'
        session.flush()
        return result

    monkeypatch.setattr(module, handler, corrupted_create)
    case = next(case for case in load_cases() if case.id == case_id)
    result = run_async(run_case(case))
    assert result.unauthorized_writes == 1
    assert not result.passed
