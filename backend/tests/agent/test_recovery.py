"""M6 崩溃窗口：业务提交后、Checkpoint 记下节点完成前可安全重放。"""

from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.agent.graph import execute_write
from app.agent.policies import hash_arguments
from app.agent_models import AgentApproval, AgentEvent, AgentRun, AgentToolExecution
from app.config import Base
from app.models import Task, User


def test_write_node_replay_after_business_commit_has_one_effect():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    run_id = str(UUID(int=91))
    arguments = {"title": "只创建一次的任务"}
    with Session(engine) as session:
        owner = User(username="recovery-owner", password_hash="hash")
        session.add(owner)
        session.flush()
        owner_id = owner.id
        session.add(
            AgentRun(
                id=run_id,
                owner_id=owner_id,
                goal="创建任务",
                status="running",
                thread_id=run_id,
                graph_version="write-v1",
                max_steps=3,
                timeout_seconds=60,
            )
        )
        session.add(
            AgentApproval(
                run_id=run_id,
                tool_call_id="call-crash",
                tool_name="create_task",
                tool_version="v1",
                arguments_json=arguments,
                arguments_hash=hash_arguments(arguments),
                status="approved",
                decision="approve",
                decision_payload={
                    "approved_arguments": arguments,
                    "arguments_hash": hash_arguments(arguments),
                },
            )
        )
        session.commit()

    @contextmanager
    def session_factory():
        with Session(engine) as session:
            yield session

    # 两次使用同一 Checkpoint 输入，模拟第一次业务事务已提交但节点完成标记丢失。
    stale_state = {
        "run_id": run_id,
        "owner_id": owner_id,
        "step_count": 0,
        "observations": [],
        "pending_tool_call": {
            "id": "call-crash",
            "name": "create_task",
            "arguments": arguments,
        },
    }
    first = execute_write(stale_state, session_factory=session_factory)
    replayed = execute_write(stale_state, session_factory=session_factory)

    assert replayed == first
    with Session(engine) as session:
        assert session.scalar(select(func.count(Task.id))) == 1
        assert session.scalar(select(func.count(AgentToolExecution.id))) == 1
        assert session.scalar(select(func.count(AgentEvent.id))) == 1
        assert session.scalar(select(Task.title)) == arguments["title"]
    engine.dispose()
