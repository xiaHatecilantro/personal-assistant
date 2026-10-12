"""Agent 后台运行时的任务生命周期测试。"""

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.schemas import RunStatus
from app.agent_models import AgentEvent, AgentRun
from app.config import Base
from app.models import User
from tests.agent.asyncio_utils import run_async


def test_task_registry_rejects_duplicate_active_run_id() -> None:
    from app.agent.runtime import DuplicateRunError, RunTaskRegistry

    async def scenario() -> None:
        release = asyncio.Event()

        async def blocking_operation() -> None:
            await release.wait()

        registry = RunTaskRegistry()
        task = registry.start("run-1", blocking_operation)

        with pytest.raises(DuplicateRunError):
            registry.start("run-1", blocking_operation)

        release.set()
        await task

    run_async(scenario())


def test_task_registry_removes_run_after_operation_finishes() -> None:
    from app.agent.runtime import RunTaskRegistry

    async def scenario() -> None:
        registry = RunTaskRegistry()

        async def completed_operation() -> None:
            return None

        task = registry.start("run-1", completed_operation)
        assert registry.is_running("run-1") is True

        await task
        await asyncio.sleep(0)

        assert registry.is_running("run-1") is False

    run_async(scenario())


def test_task_registry_rejects_new_tasks_after_shutdown() -> None:
    from app.agent.runtime import RuntimeShuttingDownError, RunTaskRegistry

    async def scenario() -> None:
        registry = RunTaskRegistry()
        await registry.shutdown()

        with pytest.raises(RuntimeShuttingDownError):
            registry.start("run-1", _wait_forever)

    run_async(scenario())


def _database_factory(tmp_path: Path):
    database_path = tmp_path / "runtime.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _commit_queued_run(
    session_factory,
    *,
    graph_version: str = "read-v1",
    timeout_seconds: int = 5,
) -> str:
    run_id = str(uuid4())
    with session_factory() as request_session:
        owner = User(username=f"owner-{run_id}", password_hash="hash")
        request_session.add(owner)
        request_session.flush()
        request_session.add(
            AgentRun(
                id=run_id,
                owner_id=owner.id,
                goal="整理本周任务",
                status=RunStatus.QUEUED.value,
                thread_id=run_id,
                graph_version=graph_version,
                max_steps=3,
                timeout_seconds=timeout_seconds,
            )
        )
        request_session.commit()
    return run_id


def test_runtime_executes_committed_run_with_a_new_session(tmp_path: Path) -> None:
    from app.agent.runtime import AgentRuntime

    engine, session_factory = _database_factory(tmp_path)
    run_id = _commit_queued_run(session_factory)

    class SuccessfulGraph:
        async def ainvoke(self, initial_state, *, config):
            # 请求 Session 已离开 with；后台只能通过新事务读到已提交的 Run。
            with session_factory() as verification_session:
                assert verification_session.get(AgentRun, run_id) is not None
            assert initial_state["run_id"] == run_id
            assert config["configurable"]["thread_id"] == run_id
            return {
                **initial_state,
                "step_count": 1,
                "plan": ["查找任务"],
                "observations": [
                    {
                        "tool_call_id": "call-1",
                        "tool_name": "list_tasks",
                        "ok": True,
                        "result": {"items": []},
                    }
                ],
                "final_answer": "已整理",
                "error": None,
            }

    async def scenario() -> None:
        runtime = AgentRuntime(
            session_factory=session_factory,
            graphs={"read-v1": SuccessfulGraph()},
        )
        await runtime.start(run_id)

    run_async(scenario())

    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        assert run.status == RunStatus.COMPLETED.value
        assert run.step_count == 1
        assert run.final_answer == "已整理"
        assert run.started_at is not None
        assert run.finished_at is not None
        assert [
            event.event_type
            for event in session.scalars(
                select(AgentEvent)
                .where(AgentEvent.run_id == run_id)
                .order_by(AgentEvent.sequence)
            )
        ] == ["run.started", "plan.updated", "tool.completed", "run.completed"]

    engine.dispose()


@pytest.mark.parametrize(
    ("graph", "timeout_seconds", "expected_error_code"),
    [
        pytest.param(
            type(
                "FailingGraph",
                (),
                {
                    "ainvoke": lambda self, initial_state, *, config: _raise_model_error(),
                },
            )(),
            5,
            "model_error",
            id="model-error",
        ),
        pytest.param(
            type(
                "SlowGraph",
                (),
                {
                    "ainvoke": lambda self, initial_state, *, config: _wait_forever(),
                },
            )(),
            1,
            "run_timeout",
            id="total-timeout",
        ),
    ],
)
def test_runtime_records_failures_as_terminal_events(
    tmp_path: Path,
    graph,
    timeout_seconds: int,
    expected_error_code: str,
) -> None:
    from app.agent.runtime import AgentRuntime

    engine, session_factory = _database_factory(tmp_path)
    run_id = _commit_queued_run(session_factory, timeout_seconds=timeout_seconds)

    async def scenario() -> None:
        runtime = AgentRuntime(
            session_factory=session_factory,
            graphs={"read-v1": graph},
        )
        await runtime.start(run_id)

    run_async(scenario())

    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        assert run.status == RunStatus.FAILED.value
        assert run.error_code == expected_error_code
        assert run.error_message
        assert run.finished_at is not None
        events = list(
            session.scalars(
                select(AgentEvent)
                .where(AgentEvent.run_id == run_id)
                .order_by(AgentEvent.sequence)
            )
        )
        assert [event.event_type for event in events] == ["run.started", "run.failed"]
        assert events[-1].payload_json["error_code"] == expected_error_code
        assert "provider-secret" not in str(events[-1].payload_json)

    engine.dispose()


async def _raise_model_error():
    raise RuntimeError("provider-secret")


async def _wait_forever():
    await asyncio.Event().wait()


@pytest.mark.parametrize(
    ("graph_version", "mutate_thread_id", "expected_error_code"),
    [
        ("retired-v0", False, "unsupported_graph_version"),
        ("read-v1", True, "invalid_thread_identity"),
    ],
)
def test_runtime_rejects_unresolvable_persisted_execution_identity(
    tmp_path: Path,
    graph_version: str,
    mutate_thread_id: bool,
    expected_error_code: str,
) -> None:
    from app.agent.runtime import AgentRuntime

    engine, session_factory = _database_factory(tmp_path)
    run_id = _commit_queued_run(session_factory, graph_version=graph_version)
    if mutate_thread_id:
        with session_factory() as session:
            run = session.get(AgentRun, run_id)
            assert run is not None
            run.thread_id = str(uuid4())
            session.commit()

    class UnexpectedGraph:
        async def ainvoke(self, initial_state, *, config):
            raise AssertionError("invalid persisted identity must not execute a graph")

    async def scenario() -> None:
        runtime = AgentRuntime(
            session_factory=session_factory,
            graphs={"read-v1": UnexpectedGraph()},
        )
        await runtime.start(run_id)

    run_async(scenario())

    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        assert run.status == RunStatus.FAILED.value
        assert run.error_code == expected_error_code
        assert run.finished_at is not None
        events = list(
            session.scalars(
                select(AgentEvent)
                .where(AgentEvent.run_id == run_id)
                .order_by(AgentEvent.sequence)
            )
        )
        assert [event.event_type for event in events] == ["run.started", "run.failed"]
        assert events[-1].payload_json["error_code"] == expected_error_code

    engine.dispose()


def test_runtime_does_not_overwrite_a_terminal_run(tmp_path: Path) -> None:
    from app.agent.runtime import AgentRuntime

    engine, session_factory = _database_factory(tmp_path)
    run_id = _commit_queued_run(session_factory)
    with session_factory() as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        run.status = RunStatus.COMPLETED.value
        run.final_answer = "先前已经完成"
        session.commit()

    class UnexpectedGraph:
        async def ainvoke(self, initial_state, *, config):
            raise AssertionError("terminal run must not execute again")

    async def scenario() -> None:
        runtime = AgentRuntime(
            session_factory=session_factory,
            graphs={"read-v1": UnexpectedGraph()},
        )
        await runtime.start(run_id)

    run_async(scenario())

    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        assert run.status == RunStatus.COMPLETED.value
        assert run.final_answer == "先前已经完成"
        assert session.scalar(
            select(AgentEvent).where(AgentEvent.run_id == run_id)
        ) is None

    engine.dispose()


def test_runtime_persists_graph_reported_error_as_failed_run(tmp_path: Path) -> None:
    from app.agent.runtime import AgentRuntime

    engine, session_factory = _database_factory(tmp_path)
    run_id = _commit_queued_run(session_factory)

    class BudgetExceededGraph:
        async def ainvoke(self, initial_state, *, config):
            return {
                **initial_state,
                "step_count": 3,
                "final_answer": "已达到最大工具调用步数，无法继续执行。",
                "error": {
                    "code": "max_steps_exceeded",
                    "message": "工具调用步数已达到上限 3",
                },
            }

    async def scenario() -> None:
        runtime = AgentRuntime(
            session_factory=session_factory,
            graphs={"read-v1": BudgetExceededGraph()},
        )
        await runtime.start(run_id)

    run_async(scenario())

    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        assert run.status == RunStatus.FAILED.value
        assert run.error_code == "max_steps_exceeded"
        assert run.error_message == "工具调用步数已达到上限 3"
        assert run.finished_at is not None
        assert [
            event.event_type
            for event in session.scalars(
                select(AgentEvent)
                .where(AgentEvent.run_id == run_id)
                .order_by(AgentEvent.sequence)
            )
        ] == ["run.started", "run.failed"]

    engine.dispose()


def test_runtime_marks_invalid_graph_output_as_failed(tmp_path: Path) -> None:
    from app.agent.runtime import AgentRuntime

    engine, session_factory = _database_factory(tmp_path)
    run_id = _commit_queued_run(session_factory)

    class InvalidOutputGraph:
        async def ainvoke(self, initial_state, *, config):
            return {
                **initial_state,
                "observations": [
                    {
                        "tool_call_id": "call-1",
                        "tool_name": "list_tasks",
                        "ok": True,
                        "result": {"raw": object()},
                    }
                ],
                "final_answer": "不会被持久化",
                "error": None,
            }

    async def scenario() -> None:
        runtime = AgentRuntime(
            session_factory=session_factory,
            graphs={"read-v1": InvalidOutputGraph()},
        )
        await runtime.start(run_id)

    run_async(scenario())

    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        assert run.status == RunStatus.FAILED.value
        assert run.error_code == "invalid_graph_output"
        assert [
            event.event_type
            for event in session.scalars(
                select(AgentEvent)
                .where(AgentEvent.run_id == run_id)
                .order_by(AgentEvent.sequence)
            )
        ] == ["run.started", "run.failed"]

    engine.dispose()


def test_runtime_shutdown_interrupts_active_run(tmp_path: Path) -> None:
    from app.agent.runtime import AgentRuntime

    engine, session_factory = _database_factory(tmp_path)
    run_id = _commit_queued_run(session_factory)

    class BlockingGraph:
        def __init__(self) -> None:
            self.started = asyncio.Event()

        async def ainvoke(self, initial_state, *, config):
            self.started.set()
            await asyncio.Event().wait()

    graph = BlockingGraph()

    async def scenario() -> None:
        runtime = AgentRuntime(
            session_factory=session_factory,
            graphs={"read-v1": graph},
        )
        task = runtime.start(run_id)
        await graph.started.wait()

        await runtime.shutdown()

        assert task.cancelled()
        assert runtime.is_running(run_id) is False

    run_async(scenario())

    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        assert run.status == RunStatus.INTERRUPTED.value
        assert run.error_code == "runtime_shutdown"
        assert run.finished_at is None
        assert [
            event.event_type
            for event in session.scalars(
                select(AgentEvent)
                .where(AgentEvent.run_id == run_id)
                .order_by(AgentEvent.sequence)
            )
        ] == ["run.started", "run.interrupted"]

    engine.dispose()


def test_resume_checkpoint_read_failure_records_public_error(tmp_path: Path) -> None:
    from app.agent.runtime import AgentRuntime

    engine, session_factory = _database_factory(tmp_path)
    run_id = _commit_queued_run(session_factory, graph_version="write-v1")
    with session_factory() as session:
        session.get(AgentRun, run_id).status = RunStatus.WAITING_APPROVAL.value
        session.commit()

    class UnavailableCheckpointGraph:
        async def aget_state(self, config):
            raise RuntimeError("postgres-credential-secret")

        async def ainvoke(self, initial_state, *, config):
            raise AssertionError("must not resume without a checkpoint")

    async def scenario() -> None:
        runtime = AgentRuntime(
            session_factory=session_factory,
            graphs={"write-v1": UnavailableCheckpointGraph()},
        )
        await runtime.resume(run_id)

    run_async(scenario())
    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        assert run.status == RunStatus.INTERRUPTED.value
        assert run.error_code == "checkpoint_unavailable"
        assert "postgres-credential-secret" not in run.error_message
        assert [event.event_type for event in session.scalars(
            select(AgentEvent).where(AgentEvent.run_id == run_id)
        )] == ["run.interrupted"]
    engine.dispose()


def test_shutdown_during_checkpoint_read_interrupts_waiting_run(tmp_path: Path) -> None:
    from app.agent.runtime import AgentRuntime

    engine, session_factory = _database_factory(tmp_path)
    run_id = _commit_queued_run(session_factory, graph_version="write-v1")
    with session_factory() as session:
        session.get(AgentRun, run_id).status = RunStatus.WAITING_APPROVAL.value
        session.commit()

    class BlockingCheckpointGraph:
        def __init__(self) -> None:
            self.read_started = asyncio.Event()

        async def aget_state(self, config):
            self.read_started.set()
            await asyncio.Event().wait()

        async def ainvoke(self, initial_state, *, config):
            raise AssertionError("must not invoke before checkpoint read")

    graph = BlockingCheckpointGraph()

    async def scenario() -> None:
        runtime = AgentRuntime(session_factory=session_factory, graphs={"write-v1": graph})
        task = runtime.resume(run_id)
        await graph.read_started.wait()
        await runtime.shutdown()
        assert task.cancelled()

    run_async(scenario())
    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        assert run.status == RunStatus.INTERRUPTED.value
        assert run.error_code == "runtime_shutdown"
        assert [event.event_type for event in session.scalars(
            select(AgentEvent).where(AgentEvent.run_id == run_id)
        )] == ["run.interrupted"]
    engine.dispose()
