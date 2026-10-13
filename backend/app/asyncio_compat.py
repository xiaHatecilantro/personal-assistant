"""为异步 psycopg 提供跨平台 Selector 事件循环入口。"""

import asyncio
import selectors
from collections.abc import Coroutine
from typing import Any, TypeVar


T = TypeVar("T")


def selector_event_loop_factory() -> asyncio.AbstractEventLoop:
    """显式创建 psycopg 支持的 SelectorEventLoop，包括 Windows。"""
    return asyncio.SelectorEventLoop(selectors.SelectSelector())


def run_async(coroutine: Coroutine[Any, Any, T]) -> T:
    with asyncio.Runner(loop_factory=selector_event_loop_factory) as runner:
        return runner.run(coroutine)
