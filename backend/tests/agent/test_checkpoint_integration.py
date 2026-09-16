"""PostgreSQL Checkpointer 的真实持久化闭环测试。"""

import asyncio
import os
from contextlib import suppress
from typing import TypedDict
from uuid import uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph


class CheckpointState(TypedDict):
    value: str


@pytest.mark.integration
def test_postgres_checkpointer_restores_state_for_the_same_thread() -> None:
    checkpoint_database_url = os.getenv("CHECKPOINT_DATABASE_URL")
    if not checkpoint_database_url:
        pytest.skip("CHECKPOINT_DATABASE_URL is not configured")

    asyncio.run(_assert_checkpoint_round_trip(checkpoint_database_url))


async def _assert_checkpoint_round_trip(checkpoint_database_url: str) -> None:
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    def persist_value(state: CheckpointState) -> CheckpointState:
        return {"value": f"{state['value']}-persisted"}

    builder = StateGraph(CheckpointState)
    builder.add_node("persist_value", persist_value)
    builder.add_edge(START, "persist_value")
    builder.add_edge("persist_value", END)

    first_serde = JsonPlusSerializer(allowed_msgpack_modules=None)
    async with AsyncPostgresSaver.from_conn_string(
        checkpoint_database_url,
        serde=first_serde,
    ) as first_checkpointer:
        await first_checkpointer.setup()
        first_graph = builder.compile(checkpointer=first_checkpointer)
        result = await first_graph.ainvoke({"value": "initial"}, config=config)

        assert result["value"] == "initial-persisted"

    second_serde = JsonPlusSerializer(allowed_msgpack_modules=None)
    async with AsyncPostgresSaver.from_conn_string(
        checkpoint_database_url,
        serde=second_serde,
    ) as second_checkpointer:
        restored_graph = builder.compile(checkpointer=second_checkpointer)
        try:
            snapshot = await restored_graph.aget_state(config)

            assert snapshot.values["value"] == "initial-persisted"
        finally:
            with suppress(Exception):
                await second_checkpointer.adelete_thread(thread_id)
