import pytest

from app.agent.policies import InvalidRunTransition, can_transition, ensure_run_transition
from app.agent.schemas import RunStatus


def test_run_status_transition_matrix_matches_planned_lifecycle():
    allowed_transitions = {
        RunStatus.QUEUED: {RunStatus.RUNNING},
        RunStatus.RUNNING: {
            RunStatus.WAITING_APPROVAL,
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.CANCELLING,
            RunStatus.INTERRUPTED,
        },
        RunStatus.WAITING_APPROVAL: {
            RunStatus.RUNNING,
            RunStatus.CANCELLING,
            RunStatus.FAILED,
            RunStatus.INTERRUPTED,
        },
        RunStatus.INTERRUPTED: {
            RunStatus.QUEUED,
            RunStatus.RUNNING,
            RunStatus.CANCELLED,
        },
        RunStatus.CANCELLING: {RunStatus.CANCELLED, RunStatus.FAILED},
        RunStatus.COMPLETED: set(),
        RunStatus.FAILED: set(),
        RunStatus.CANCELLED: set(),
    }

    for source in RunStatus:
        for target in RunStatus:
            expected = target in allowed_transitions[source]
            result = can_transition(source, target)

            assert type(result) is bool
            assert result is expected
            if expected:
                assert ensure_run_transition(source, target) is None


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (RunStatus.COMPLETED, RunStatus.RUNNING),
        (RunStatus.FAILED, RunStatus.QUEUED),
        (RunStatus.CANCELLED, RunStatus.RUNNING),
        (RunStatus.RUNNING, RunStatus.RUNNING),
        (RunStatus.COMPLETED, RunStatus.COMPLETED),
        (RunStatus.QUEUED, RunStatus.COMPLETED),
    ],
)
def test_invalid_transition_is_rejected(source, target):
    assert can_transition(source, target) is False

    with pytest.raises(InvalidRunTransition):
        ensure_run_transition(source, target)
