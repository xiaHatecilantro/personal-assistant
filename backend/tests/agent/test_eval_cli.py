"""CI 依据退出码阻止失败评测，而不是只输出一份看起来正常的报告。"""

import json

import pytest

from evals import cli
from evals.metrics import CATEGORY_COUNTS

pytestmark = pytest.mark.evaluation


def suite():
    return [dict(
        case_id=f"{category}-{i}", category=category, passed=True,
        failure_reasons=[], status="completed", step_count=2, duration_ms=10,
        expected_tools_match=True, unauthorized_writes=0, write_checks=1,
        authorization_checks=1, authorization_blocks=1,
        idempotency_checks=1, idempotency_passes=1,
    ) for category, count in CATEGORY_COUNTS.items() for i in range(count)]


def test_cli_writes_report_and_returns_success(monkeypatch, tmp_path):
    async def run_suite(cases, *, seed):
        assert len(cases) == 30
        assert seed == 7
        return suite()

    monkeypatch.setattr(cli.runner, "run_suite", run_suite, raising=False)
    output = tmp_path / "report.json"
    assert cli.main(["--seed", "7", "--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["passed"]
    assert len(report["cases_sha256"]) == 64
    assert len(report["results"]) == 30


def test_cli_failing_gate_returns_nonzero(monkeypatch, capsys):
    async def run_suite(cases, *, seed):
        results = suite()
        results[0]["unauthorized_writes"] = 1
        return results

    monkeypatch.setattr(cli.runner, "run_suite", run_suite, raising=False)
    assert cli.main([]) == 1
    assert "unauthorized_writes" in capsys.readouterr().out


def test_cli_invalid_cases_return_configuration_error(tmp_path, capsys):
    source = tmp_path / "invalid.json"
    source.write_text("{}", encoding="utf-8")
    assert cli.main(["--cases", str(source)]) == 2
    assert "评测无法执行" in capsys.readouterr().err
