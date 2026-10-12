"""异步 PostgreSQL 所需事件循环的进程入口测试。"""

import asyncio


def test_selector_event_loop_factory_never_returns_proactor_loop():
    from app.asyncio_compat import selector_event_loop_factory

    loop = selector_event_loop_factory()
    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
        if hasattr(asyncio, "ProactorEventLoop"):
            assert not isinstance(loop, asyncio.ProactorEventLoop)
    finally:
        loop.close()
