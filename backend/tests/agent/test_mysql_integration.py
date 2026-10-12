"""M10 真实 MySQL 验收：行锁、状态竞争与写工具并发幂等。

只接受 MYSQL_TEST_DATABASE_URL 指向的 m10_acceptance 隔离库；表必须事先迁移。
测试不建库、不建表，结束时仅删除本次 UUID 用户及其运行、任务和审计记录。
"""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, delete, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import sessionmaker

from app.agent.policies import hash_arguments
from app.agent.repository import append_event, compare_and_set_status, create_approval, create_run
from app.agent.schemas import RunStatus
from app.agent.tools.base import ToolContext
from app.agent.tools.tasks import execute_approved_write
from app.agent_models import AgentApproval, AgentEvent, AgentRun, AgentToolExecution
from app.models import Task, User


pytestmark = pytest.mark.integration
_WORKERS = 6
_TABLES = {"users", "tasks", "agent_runs", "agent_events", "agent_approvals", "agent_tool_executions", "alembic_version"}


@pytest.fixture
def mysql_run():
    raw = os.getenv("MYSQL_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("MYSQL_TEST_DATABASE_URL is not configured")
    try:
        url = make_url(raw)
    except ArgumentError:
        pytest.fail("MYSQL_TEST_DATABASE_URL is not a valid SQLAlchemy URL", pytrace=False)
    if url.drivername != "mysql+pymysql" or url.database != "m10_acceptance":
        pytest.fail("MySQL integration tests require mysql+pymysql and database m10_acceptance", pytrace=False)

    engine = create_engine(
        url, pool_pre_ping=True, pool_size=_WORKERS, max_overflow=0, pool_timeout=10,
        connect_args={"connect_timeout": 10, "read_timeout": 20, "write_timeout": 20},
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    owner_id = None
    username = f"m10-{uuid4().hex}"
    run_id = str(uuid4())
    try:
        # URL 查询参数可能覆盖驱动的库名，因此在任何写入前核对连接实际选中的库。
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT DATABASE()")) == "m10_acceptance", "unexpected database selected"
            assert _TABLES <= set(inspect(connection).get_table_names()), "run Alembic migrations before MySQL acceptance"
        with factory() as session:
            owner = User(username=username, password_hash="integration-test-unused")
            session.add(owner)
            session.flush()
            owner_id = owner.id
            create_run(session, run_id=run_id, owner_id=owner_id, goal="M10 MySQL 并发验收",
                       graph_version="write-v1", max_steps=5, timeout_seconds=30)
            session.commit()
        yield factory, owner_id, run_id
    finally:
        if owner_id is not None:
            with factory() as session:
                # 使用明确的 UUID Run 和测试用户过滤，不触碰同库中的其他验收记录。
                for model in (AgentToolExecution, AgentApproval, AgentEvent):
                    session.execute(delete(model).where(model.run_id == run_id))
                session.execute(delete(AgentRun).where(AgentRun.id == run_id, AgentRun.owner_id == owner_id))
                session.execute(delete(Task).where(Task.owner_id == owner_id))
                session.execute(delete(User).where(User.id == owner_id, User.username == username))
                session.commit()
        engine.dispose()


def _race(factory, operation, *, workers=_WORKERS):
    barrier = Barrier(workers)

    def perform(index):
        with factory() as session:
            # 先拿到各自连接再同步开始，不能让连接池排队把“并发”变成串行调用。
            session.connection()
            barrier.wait(timeout=10)
            result = operation(session, index)
            session.commit()
            return result

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(perform, index) for index in range(workers)]
        return [future.result(timeout=30) for future in futures]


def test_mysql_concurrent_event_append_allocates_unique_contiguous_sequences(mysql_run):
    factory, _, run_id = mysql_run

    def record(session, index):
        return append_event(session, run_id=run_id, event_type="run.started",
                            payload_json={"worker": index}).sequence

    sequences = _race(factory, record)
    assert sorted(sequences) == list(range(1, _WORKERS + 1))
    with factory() as session:
        events = session.scalars(select(AgentEvent).where(AgentEvent.run_id == run_id).order_by(AgentEvent.sequence)).all()
        assert [event.sequence for event in events] == list(range(1, _WORKERS + 1))
        assert sorted(event.payload_json["worker"] for event in events) == list(range(_WORKERS))


def test_mysql_competing_status_cas_has_exactly_one_winner(mysql_run):
    factory, owner_id, run_id = mysql_run

    def transition(session, _index):
        return compare_and_set_status(
            session, run_id=run_id, owner_id=owner_id,
            expected_status=RunStatus.QUEUED, new_status=RunStatus.RUNNING,
        )

    winners = _race(factory, transition, workers=2)
    assert sorted(winners) == [False, True]
    with factory() as session:
        assert session.get(AgentRun, run_id).status == "running"


def test_mysql_concurrent_approved_tool_replay_creates_one_task_and_one_execution(mysql_run):
    factory, owner_id, run_id = mysql_run
    call_id = f"m10-call-{uuid4().hex}"
    arguments = {"title": f"m10-task-{run_id}", "description": "并发重放只允许一次副作用"}
    approved_hash = hash_arguments(arguments)
    context = ToolContext(owner_id=owner_id, run_id=UUID(run_id))
    with factory() as session:
        session.get(AgentRun, run_id).status = "running"
        approval = create_approval(
            session, run_id=run_id, tool_call_id=call_id, tool_name="create_task",
            tool_version="v1", arguments_json=arguments, arguments_hash=approved_hash,
        )
        approval.status = "approved"
        approval.decision = "approve"
        approval.decision_payload = {"approved_arguments": arguments, "arguments_hash": approved_hash}
        session.commit()

    def execute(session, _index):
        return execute_approved_write(session, context, call_id, "create_task")

    results = _race(factory, execute)
    assert all(result == results[0] for result in results)
    assert results[0]["ok"] is True
    with factory() as session:
        # 再顺序重放一次；既检查实际业务实体，也检查同事务台账和公开事件。
        assert execute_approved_write(session, context, call_id, "create_task") == results[0]
        session.commit()
        tasks = session.scalars(select(Task).where(Task.owner_id == owner_id)).all()
        assert len(tasks) == 1
        assert tasks[0].id == results[0]["result"]["task_id"]
        assert tasks[0].title == arguments["title"]
        assert tasks[0].description == arguments["description"]
        executions = session.scalars(select(AgentToolExecution).where(AgentToolExecution.run_id == run_id)).all()
        assert len(executions) == 1
        assert executions[0].result_json == results[0]
        assert executions[0].business_entity_id == str(tasks[0].id)
        assert session.scalar(select(func.count(AgentEvent.id)).where(
            AgentEvent.run_id == run_id, AgentEvent.event_type == "tool.completed",
        )) == 1
