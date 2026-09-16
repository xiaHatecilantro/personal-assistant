from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from app.settings import get_settings


@asynccontextmanager
async def open_agent_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    database_url = get_settings().checkpoint_database_url
    serializer = JsonPlusSerializer(allowed_msgpack_modules=None)
    async with AsyncPostgresSaver.from_conn_string(
        database_url,
        serde=serializer,
    ) as checkpointer:
        yield checkpointer


async def setup_agent_checkpoint_database() -> None:
    async with open_agent_checkpointer() as checkpointer:
        await checkpointer.setup()


if __name__ == "__main__":
    import asyncio

    asyncio.run(setup_agent_checkpoint_database())
