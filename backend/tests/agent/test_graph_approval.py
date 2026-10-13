"""写 Graph 的审批暂停、恢复与业务副作用边界。"""

from contextlib import contextmanager
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.agent.graph import build_graph_config, compile_write_graph
from app.agent.model_gateway import FinalDecision, ModelToolCall, ToolDecision
from app.agent.policies import hash_arguments
from app.agent.repository import create_run
from app.agent_models import AgentApproval, AgentRun, AgentToolExecution
from app.config import Base
from app.models import Task, User
from tests.agent.asyncio_utils import run_async
from tests.agent.fakes import ScriptedModelGateway


def _start_write_graph(*, arguments: dict[str, object], final_answer: str):
    # LangGraph 在线程池运行同步节点；内存数据库必须共用同一连接。
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    run_id = str(uuid4())
    with Session(engine) as session:
        owner = User(username=f"graph-write-{run_id}", password_hash="hash")
        session.add(owner)
        session.flush()
        owner_id = owner.id
        run = create_run(
            session,
            run_id=run_id,
            owner_id=owner_id,
            goal="创建一条任务",
            graph_version="write-v1",
            max_steps=2,
            timeout_seconds=60,
        )
        run.status = "running"
        session.commit()

    @contextmanager
    def session_factory():
        with Session(engine) as session:
            yield session

    gateway = ScriptedModelGateway(
        [
            ToolDecision(
                tool_call=ModelToolCall(
                    id="call-write-1",
                    name="create_task",
                    arguments=arguments,
                )
            ),
            FinalDecision(final_answer=final_answer),
        ]
    )
    graph = compile_write_graph(
        model_gateway=gateway,
        session_factory=session_factory,
        checkpointer=InMemorySaver(),
    )
    config = build_graph_config(run_id=run_id, max_steps=2)
    state = {
        "run_id": run_id,
        "owner_id": owner_id,
        "goal": "创建一条任务",
        "step_count": 0,
        "plan": [],
        "messages": [],
        "pending_tool_call": None,
        "observations": [],
        "final_answer": None,
        "error": None,
    }

    paused = run_async(graph.ainvoke(state, config=config))
    assert paused["__interrupt__"]
    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        run.status = "waiting_approval"
        session.commit()
    return engine, graph, config


def _approval_id(engine) -> str:
    with Session(engine) as session:
        approval = session.scalar(select(AgentApproval))
        assert approval is not None
        return approval.id


def test_approved_write_waits_for_human_before_creating_task() -> None:
    engine, graph, config = _start_write_graph(
        arguments={"title": "准备周报"}, final_answer="任务已创建"
    )
    with Session(engine) as session:
        approval = session.scalar(select(AgentApproval))
        assert approval is not None
        approval_id = approval.id
        assert approval.tool_call_id == "call-write-1"
        assert session.scalar(select(func.count(Task.id))) == 0
        assert session.scalar(select(func.count(AgentToolExecution.id))) == 0
        approval.status = "approved"
        approval.decision = "approve"
        approval.decision_payload = {
            "approved_arguments": {"title": "准备周报"},
            "arguments_hash": hash_arguments({"title": "准备周报"}),
        }
        session.get(AgentRun, approval.run_id).status = "running"
        session.commit()

    result = run_async(graph.ainvoke(Command(resume={"approval_id": approval_id}), config=config))
    assert result["final_answer"] == "任务已创建"
    assert result["step_count"] == 1
    assert result["observations"][0]["ok"] is True
    with Session(engine) as session:
        assert session.scalar(select(Task.title)) == "准备周报"
        assert session.scalar(select(func.count(AgentToolExecution.id))) == 1
    engine.dispose()


def test_rejected_write_returns_observation_without_business_write() -> None:
    engine, graph, config = _start_write_graph(
        arguments={"title": "不应创建"}, final_answer="已取消创建"
    )
    approval_id = _approval_id(engine)
    with Session(engine) as session:
        approval = session.get(AgentApproval, approval_id)
        approval.status = "rejected"
        approval.decision = "reject"
        session.get(AgentRun, approval.run_id).status = "running"
        session.commit()

    result = run_async(graph.ainvoke(Command(resume={"approval_id": approval_id}), config=config))

    assert result["final_answer"] == "已取消创建"
    assert result["step_count"] == 1
    assert result["observations"][0]["error"]["code"] == "approval_rejected"
    with Session(engine) as session:
        assert session.scalar(select(func.count(Task.id))) == 0
        assert session.scalar(select(func.count(AgentToolExecution.id))) == 0
    engine.dispose()


def test_edited_approval_uses_persisted_snapshot_instead_of_model_arguments() -> None:
    engine, graph, config = _start_write_graph(
        arguments={"title": "模型原提议"}, final_answer="已按修改创建"
    )
    approval_id = _approval_id(engine)
    with Session(engine) as session:
        approval = session.get(AgentApproval, approval_id)
        approval.status = "approved"
        approval.decision = "edit"
        approval.decision_payload = {
            "approved_arguments": {"title": "用户修改后"},
            "arguments_hash": hash_arguments({"title": "用户修改后"}),
        }
        session.get(AgentRun, approval.run_id).status = "running"
        session.commit()

    result = run_async(graph.ainvoke(Command(resume={"approval_id": approval_id}), config=config))

    assert result["final_answer"] == "已按修改创建"
    assert result["observations"][0]["ok"] is True
    with Session(engine) as session:
        assert session.scalar(select(Task.title)) == "用户修改后"
        assert session.scalar(select(func.count(Task.id))) == 1
    engine.dispose()


def test_write_graph_exposes_five_read_and_three_write_tool_schemas(monkeypatch) -> None:
    from app.agent import graph as graph_module

    # 仅隔离本例的路由/Schema 断言；真实取消门禁在 test_cancel 中覆盖。
    monkeypatch.setattr(
        graph_module, "ensure_run_not_cancelled", lambda state, *, session_factory: None
    )
    class RecordingGateway(ScriptedModelGateway):
        tool_names: list[str]
        system_message: str

        async def decide(self, *, messages, tools):
            self.tool_names = [tool["function"]["name"] for tool in tools]
            self.system_message = messages[0]["content"]
            return await super().decide(messages=messages, tools=tools)

    @contextmanager
    def forbidden_session_factory():
        raise AssertionError("final branch must not open a database session")
        yield

    gateway = RecordingGateway([FinalDecision(final_answer="完成")])
    graph = compile_write_graph(
        model_gateway=gateway, session_factory=forbidden_session_factory
    )
    result = run_async(
        graph.ainvoke(
            {"goal": "完成", "messages": [], "step_count": 0},
            config={"configurable": {"max_steps": 1}},
        )
    )

    assert result["final_answer"] == "完成"
    assert set(gateway.tool_names) == {
        "search_notes",
        "get_note",
        "list_tasks",
        "get_task",
        "lint_knowledge",
        "create_task",
        "update_task",
        "create_note",
    }
    assert len(gateway.tool_names) == 8
    assert "写工具" in gateway.system_message
    assert "人工审批" in gateway.system_message
