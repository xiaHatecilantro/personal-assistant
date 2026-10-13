"""M8 重启恢复：旧进程只留下持久事实，新进程按原 Checkpoint 显式续跑。"""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from langgraph.types import Command
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.agent.runtime import AgentRuntime
from app.agent.graph import compile_write_graph
from app.agent.model_gateway import FinalDecision, ModelToolCall, ToolDecision
from app.agent.policies import hash_arguments
from app.agent_models import AgentApproval, AgentEvent, AgentRun
from app.config import Base
from app.models import Task, User
from tests.agent.asyncio_utils import run_async
from tests.agent.fakes import ScriptedModelGateway


def _database(tmp_path: Path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'restart.db').as_posix()}")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _run(factory, *, status: str, graph_version: str = "write-v1") -> str:
    run_id = str(uuid4())
    with factory() as session:
        owner = User(username=f"owner-{run_id}", password_hash="hash")
        session.add(owner)
        session.flush()
        session.add(AgentRun(
            id=run_id, owner_id=owner.id, goal="恢复测试", status=status,
            thread_id=run_id, graph_version=graph_version,
            max_steps=3, timeout_seconds=30,
        ))
        session.commit()
    return run_id


def _output(run_id: str) -> dict:
    return {
        "run_id": run_id, "step_count": 1, "plan": [], "observations": [],
        "final_answer": "恢复完成", "error": None,
    }


class SnapshotGraph:
    def __init__(self, snapshot, result):
        self.snapshot = snapshot
        self.result = result
        self.inputs = []
        self.thread_ids = []

    async def aget_state(self, config):
        self.thread_ids.append(config["configurable"]["thread_id"])
        return self.snapshot

    async def ainvoke(self, value, *, config):
        self.inputs.append(value)
        self.thread_ids.append(config["configurable"]["thread_id"])
        return self.result


async def _resume(runtime: AgentRuntime, run_id: str) -> None:
    await runtime.resume_interrupted(run_id)


def test_startup_reconciles_stale_running_and_cancelling_without_resuming_waiting(tmp_path):
    engine, factory = _database(tmp_path)
    running_id = _run(factory, status="running")
    cancelling_id = _run(factory, status="cancelling")
    waiting_id = _run(factory, status="waiting_approval")
    decided_id = _run(factory, status="waiting_approval")
    with factory() as session:
        session.get(AgentRun, cancelling_id).cancel_requested_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add_all([
            AgentApproval(
                run_id=waiting_id, tool_call_id="call-pending", tool_name="create_task",
                tool_version="v1", arguments_json={"title": "待审"}, arguments_hash="a" * 64,
            ),
            AgentApproval(
                run_id=decided_id, tool_call_id="call-decided", tool_name="create_task",
                tool_version="v1", arguments_json={"title": "已审"}, arguments_hash="b" * 64,
                status="approved", decision="approve",
            ),
        ])
        session.commit()

    runtime = AgentRuntime(session_factory=factory, graphs={})
    runtime.reconcile_startup()
    runtime.reconcile_startup()  # 重复启动纠偏不应复制事件。

    with factory() as session:
        assert session.get(AgentRun, running_id).status == "interrupted"
        assert session.get(AgentRun, cancelling_id).status == "cancelled"
        assert session.get(AgentRun, waiting_id).status == "waiting_approval"
        assert session.get(AgentRun, decided_id).status == "interrupted"
        assert [event.event_type for event in session.scalars(
            select(AgentEvent).where(AgentEvent.run_id == running_id)
        )] == ["run.interrupted"]
        assert [event.event_type for event in session.scalars(
            select(AgentEvent).where(AgentEvent.run_id == cancelling_id)
        )] == ["run.cancelled"]
        assert [event.event_type for event in session.scalars(
            select(AgentEvent).where(AgentEvent.run_id == decided_id)
        )] == ["run.interrupted"]
    engine.dispose()


def test_explicit_resume_uses_original_thread_and_unfinished_checkpoint(tmp_path):
    engine, factory = _database(tmp_path)
    run_id = _run(factory, status="interrupted")
    graph = SnapshotGraph(
        SimpleNamespace(values=_output(run_id), next=("observe",), tasks=()),
        _output(run_id),
    )
    runtime = AgentRuntime(session_factory=factory, graphs={"write-v1": graph})
    run_async(_resume(runtime, run_id))

    with factory() as session:
        assert session.get(AgentRun, run_id).status == "completed"
    assert graph.inputs == [None]
    assert graph.thread_ids == [run_id, run_id]
    engine.dispose()


def test_pending_approval_is_restored_to_waiting_without_graph_execution(tmp_path):
    engine, factory = _database(tmp_path)
    run_id = _run(factory, status="interrupted")
    with factory() as session:
        session.add(AgentApproval(
            run_id=run_id, tool_call_id="call-pending", tool_name="create_task",
            tool_version="v1", arguments_json={"title": "安全任务"}, arguments_hash="a" * 64,
        ))
        session.commit()
        approval_id = session.scalar(select(AgentApproval.id).where(AgentApproval.run_id == run_id))
    graph = SnapshotGraph(
        SimpleNamespace(
            values={"pending_tool_call": {"approval_id": approval_id}},
            next=("wait_approval",), tasks=(SimpleNamespace(interrupts=(object(),)),),
        ),
        _output(run_id),
    )
    runtime = AgentRuntime(session_factory=factory, graphs={"write-v1": graph})
    run_async(_resume(runtime, run_id))

    with factory() as session:
        assert session.get(AgentRun, run_id).status == "waiting_approval"
    assert graph.inputs == []
    engine.dispose()


def test_resolved_approval_checkpoint_resumes_with_command(tmp_path):
    engine, factory = _database(tmp_path)
    run_id = _run(factory, status="interrupted")
    with factory() as session:
        approval = AgentApproval(
            run_id=run_id, tool_call_id="call-approved", tool_name="create_task",
            tool_version="v1", arguments_json={"title": "安全任务"}, arguments_hash="a" * 64,
            status="approved", decision="approve",
            decision_payload={"approved_arguments": {"title": "安全任务"}, "arguments_hash": "a" * 64},
        )
        session.add(approval)
        session.commit()
        approval_id = approval.id
    graph = SnapshotGraph(
        SimpleNamespace(
            values={"pending_tool_call": {"approval_id": approval_id}},
            next=("wait_approval",), tasks=(SimpleNamespace(interrupts=(object(),)),),
        ),
        _output(run_id),
    )
    runtime = AgentRuntime(session_factory=factory, graphs={"write-v1": graph})
    run_async(_resume(runtime, run_id))

    with factory() as session:
        assert session.get(AgentRun, run_id).status == "completed"
    assert len(graph.inputs) == 1
    assert isinstance(graph.inputs[0], Command)
    assert graph.inputs[0].resume == {"approval_id": approval_id}
    engine.dispose()


def test_checkpoint_already_at_end_only_projects_result(tmp_path):
    engine, factory = _database(tmp_path)
    run_id = _run(factory, status="interrupted")
    graph = SnapshotGraph(SimpleNamespace(values=_output(run_id), next=(), tasks=()), _output(run_id))
    runtime = AgentRuntime(session_factory=factory, graphs={"write-v1": graph})
    run_async(_resume(runtime, run_id))

    with factory() as session:
        assert session.get(AgentRun, run_id).status == "completed"
        assert session.get(AgentRun, run_id).final_answer == "恢复完成"
    assert graph.inputs == []
    engine.dispose()


def test_new_runtime_resumes_real_graph_after_approval_commit_crash(tmp_path):
    """模拟 MySQL 审批已提交、后台 Command 尚未调度时进程退出。"""
    engine, factory = _database(tmp_path)
    run_id = _run(factory, status="queued")
    saver = InMemorySaver()
    arguments = {"title": "重启后仅创建一次"}
    first_graph = compile_write_graph(
        model_gateway=ScriptedModelGateway([ToolDecision(tool_call=ModelToolCall(
            id="call-restart", name="create_task", arguments=arguments,
        ))]),
        session_factory=factory, checkpointer=saver,
    )
    first_runtime = AgentRuntime(session_factory=factory, graphs={"write-v1": first_graph})

    async def pause_for_approval():
        await first_runtime.start(run_id)

    run_async(pause_for_approval())
    with factory() as session:
        assert session.get(AgentRun, run_id).status == "waiting_approval"
        approval = session.scalar(select(AgentApproval).where(AgentApproval.run_id == run_id))
        approval.status = "approved"
        approval.decision = "approve"
        approval.decision_payload = {
            "approved_arguments": arguments, "arguments_hash": hash_arguments(arguments),
        }
        session.commit()

    # 新 Runtime 复用同一 thread_id 的 Checkpoint，不从 goal 重新触发写工具。
    second_graph = compile_write_graph(
        model_gateway=ScriptedModelGateway([FinalDecision(final_answer="已恢复完成")]),
        session_factory=factory, checkpointer=saver,
    )
    second_runtime = AgentRuntime(session_factory=factory, graphs={"write-v1": second_graph})
    second_runtime.reconcile_startup()
    with factory() as session:
        assert session.get(AgentRun, run_id).status == "interrupted"
    run_async(_resume(second_runtime, run_id))

    with factory() as session:
        assert session.get(AgentRun, run_id).status == "completed"
        assert [task.title for task in session.scalars(select(Task))] == [arguments["title"]]
    engine.dispose()
