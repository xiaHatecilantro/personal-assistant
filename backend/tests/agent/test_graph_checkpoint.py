"""只读 Agent Graph 的 Checkpoint 配置、隔离与真实 PostgreSQL 恢复测试。"""

import os
from contextlib import contextmanager, suppress
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from app.agent.model_gateway import FinalDecision
from tests.agent.asyncio_utils import run_async
from tests.agent.fakes import ScriptedModelGateway


@pytest.fixture(autouse=True)
def isolate_checkpoint_tests_from_cancel_database_check(monkeypatch):
    # 这里验证 Checkpoint 线程隔离；持久取消门禁由 test_cancel 的真实 Run 表测试。
    from app.agent import graph

    monkeypatch.setattr(graph, "ensure_run_not_cancelled", lambda state, *, session_factory: None)


def _initial_state(run_id: str):
    return {
        "run_id": run_id,
        "owner_id": 7,
        "goal": "checkpoint goal",
        "step_count": 0,
        "plan": [],
        "messages": [],
        "pending_tool_call": None,
        "observations": [],
        "final_answer": None,
        "error": None,
    }


@contextmanager
def _forbidden_session_factory():
    raise AssertionError("final-only checkpoint test must not open MySQL")
    yield


def test_graph_config_uses_server_run_id_and_max_steps() -> None:
    from app.agent.graph import build_graph_config

    config = build_graph_config(
        run_id="server-owned-run-id",
        max_steps=5,
    )

    assert config == {
        "configurable": {
            "thread_id": "server-owned-run-id",
            "max_steps": 5,
        }
    }


def test_in_memory_checkpoint_restores_same_thread_and_isolates_another() -> None:
    from app.agent.graph import build_graph_config, compile_read_graph

    saver = InMemorySaver()
    run_id = "run-same"
    same_config = build_graph_config(run_id=run_id, max_steps=2)
    other_config = build_graph_config(run_id="run-other", max_steps=2)
    first_graph = compile_read_graph(
        model_gateway=ScriptedModelGateway([FinalDecision(final_answer="persisted")]),
        session_factory=_forbidden_session_factory,
        checkpointer=saver,
    )
    run_async(first_graph.ainvoke(_initial_state(run_id), config=same_config))

    restored_graph = compile_read_graph(
        model_gateway=ScriptedModelGateway([]),
        session_factory=_forbidden_session_factory,
        checkpointer=saver,
    )
    # 对已完成线程以 ``None`` 继续调用，LangGraph 从同一 namespace 恢复最终状态。
    restored = run_async(restored_graph.ainvoke(None, config=same_config))
    other_checkpoint = run_async(saver.aget_tuple(other_config))

    assert restored["final_answer"] == "persisted"
    assert restored["run_id"] == run_id
    assert other_checkpoint is None


@pytest.mark.integration
def test_postgres_checkpoint_restores_agent_graph_and_isolates_threads() -> None:
    checkpoint_database_url = os.getenv("CHECKPOINT_DATABASE_URL")
    if not checkpoint_database_url:
        pytest.skip("CHECKPOINT_DATABASE_URL is not configured")

    run_async(_assert_postgres_agent_graph_round_trip(checkpoint_database_url))


async def _assert_postgres_agent_graph_round_trip(checkpoint_database_url: str) -> None:
    from app.agent.graph import build_graph_config, compile_read_graph

    run_id = str(uuid4())
    other_run_id = str(uuid4())
    config = build_graph_config(run_id=run_id, max_steps=2)
    other_config = build_graph_config(
        run_id=other_run_id,
        max_steps=2,
    )
    serde = JsonPlusSerializer(allowed_msgpack_modules=None)
    async with AsyncPostgresSaver.from_conn_string(
        checkpoint_database_url,
        serde=serde,
    ) as first_saver:
        await first_saver.setup()
        graph = compile_read_graph(
            model_gateway=ScriptedModelGateway(
                [FinalDecision(final_answer="postgres-persisted")]
            ),
            session_factory=_forbidden_session_factory,
            checkpointer=first_saver,
        )
        result = await graph.ainvoke(_initial_state(run_id), config=config)
        assert result["final_answer"] == "postgres-persisted"

    second_serde = JsonPlusSerializer(allowed_msgpack_modules=None)
    async with AsyncPostgresSaver.from_conn_string(
        checkpoint_database_url,
        serde=second_serde,
    ) as second_saver:
        restored_graph = compile_read_graph(
            model_gateway=ScriptedModelGateway([]),
            session_factory=_forbidden_session_factory,
            checkpointer=second_saver,
        )
        try:
            restored = await restored_graph.ainvoke(None, config=config)
            other_checkpoint = await second_saver.aget_tuple(other_config)

            assert restored["final_answer"] == "postgres-persisted"
            assert restored["run_id"] == run_id
            assert other_checkpoint is None
        finally:
            with suppress(Exception):
                await second_saver.adelete_thread(run_id)
            with suppress(Exception):
                await second_saver.adelete_thread(other_run_id)
