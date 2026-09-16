"""LangGraph PostgreSQL Checkpointer 的生命周期契约测试。"""

import asyncio
from types import SimpleNamespace


def test_open_agent_checkpointer_uses_configured_database_url(monkeypatch) -> None:
    from app.agent import checkpoint

    configured_url = "postgresql://agent:secret@checkpoint-db:5432/checkpoints"
    saver = object()
    calls: list[object] = []

    class FakeSaverContext:
        async def __aenter__(self):
            calls.append("enter")
            return saver

        async def __aexit__(self, exc_type, exc_value, traceback):
            calls.append("exit")

    class FakeAsyncPostgresSaver:
        @classmethod
        def from_conn_string(cls, connection_string: str, **kwargs):
            calls.append(connection_string)
            return FakeSaverContext()

    monkeypatch.setattr(
        checkpoint,
        "get_settings",
        lambda: SimpleNamespace(checkpoint_database_url=configured_url),
    )
    monkeypatch.setattr(checkpoint, "AsyncPostgresSaver", FakeAsyncPostgresSaver)

    async def use_checkpointer() -> None:
        async with checkpoint.open_agent_checkpointer() as opened_saver:
            assert opened_saver is saver

    asyncio.run(use_checkpointer())

    assert calls == [configured_url, "enter", "exit"]


def test_open_agent_checkpointer_disables_msgpack_module_loading(monkeypatch) -> None:
    from app.agent import checkpoint

    configured_url = "postgresql://agent:secret@checkpoint-db:5432/checkpoints"
    serializer = object()
    received: dict[str, object] = {}

    def fake_json_plus_serializer(*, allowed_msgpack_modules):
        received["allowed_msgpack_modules"] = allowed_msgpack_modules
        return serializer

    class FakeSaverContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc_value, traceback):
            return None

    class FakeAsyncPostgresSaver:
        @classmethod
        def from_conn_string(cls, connection_string: str, *, serde=None):
            received["connection_string"] = connection_string
            received["serde"] = serde
            return FakeSaverContext()

    monkeypatch.setattr(
        checkpoint,
        "get_settings",
        lambda: SimpleNamespace(checkpoint_database_url=configured_url),
    )
    monkeypatch.setattr(checkpoint, "JsonPlusSerializer", fake_json_plus_serializer)
    monkeypatch.setattr(checkpoint, "AsyncPostgresSaver", FakeAsyncPostgresSaver)

    async def use_checkpointer() -> None:
        async with checkpoint.open_agent_checkpointer():
            pass

    asyncio.run(use_checkpointer())

    assert received["connection_string"] == configured_url
    assert received["allowed_msgpack_modules"] is None
    assert received["serde"] is serializer


def test_setup_agent_checkpoint_database_initializes_schema(monkeypatch) -> None:
    from app.agent import checkpoint

    calls: list[str] = []

    class FakeSaver:
        async def setup(self) -> None:
            calls.append("setup")

    class FakeSaverContext:
        async def __aenter__(self):
            calls.append("enter")
            return FakeSaver()

        async def __aexit__(self, exc_type, exc_value, traceback):
            calls.append("exit")

    monkeypatch.setattr(
        checkpoint,
        "open_agent_checkpointer",
        lambda: FakeSaverContext(),
    )

    asyncio.run(checkpoint.setup_agent_checkpoint_database())

    assert calls == ["enter", "setup", "exit"]
