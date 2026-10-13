"""评测数据是可审查的行为契约，不能把运行结果写进期望值。"""

from collections import Counter

import pytest

from evals.runner import load_cases


pytestmark = pytest.mark.evaluation


def test_initial_read_plan_cases_have_unique_inputs_tools_terminal_states_and_assertions():
    cases = load_cases()
    read_cases = [case for case in cases if case.category == "read_plan"]
    assert len(read_cases) == 10
    assert len({case.id for case in cases}) == len(cases)
    assert all(case.input and case.assertions and case.expected_status for case in cases)
    assert all(isinstance(case.expected_tools, list) for case in cases)


def test_suite_has_thirty_cases_covering_planned_risk_categories():
    assert Counter(case.category for case in load_cases()) == {
        "read_plan": 10, "write_approval": 8, "permissions": 4,
        "recovery": 4, "injection_budget": 4,
    }


def test_case_file_rejects_an_object_instead_of_a_case_array(monkeypatch):
    monkeypatch.setattr("pathlib.Path.read_text", lambda *args, **kwargs: "{}")
    with pytest.raises(ValueError, match="array"):
        load_cases("invalid.json")
