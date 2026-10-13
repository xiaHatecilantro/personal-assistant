"""LangGraph PostgreSQL Checkpointer 的连接生命周期和表结构初始化入口。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from app.settings import get_settings


@asynccontextmanager
async def open_agent_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    """按调用范围打开并关闭 Checkpointer 连接。

    ``allowed_msgpack_modules=None`` 禁止反序列化任意 Python 模块，避免受污染的
    Checkpoint 数据触发不安全对象加载。
    """
    database_url = get_settings().checkpoint_database_url
    serializer = JsonPlusSerializer(allowed_msgpack_modules=None)
    async with AsyncPostgresSaver.from_conn_string(
        database_url,
        serde=serializer,
    ) as checkpointer:
        yield checkpointer


async def setup_agent_checkpoint_database() -> None:
    """创建或升级 LangGraph 自有表；容器启动时在 API 进程之前执行。"""
    async with open_agent_checkpointer() as checkpointer:
        await checkpointer.setup()


if __name__ == "__main__":
    from app.asyncio_compat import run_async

    run_async(setup_agent_checkpoint_database())
