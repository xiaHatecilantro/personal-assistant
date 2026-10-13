"""测试环境中的跨平台异步入口。"""

import asyncio
import selectors
import sys
from collections.abc import Coroutine
from typing import Any, TypeVar


T = TypeVar("T")


def _new_windows_selector_loop() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop(selectors.SelectSelector())


def run_async(coroutine: Coroutine[Any, Any, T]) -> T:
    """运行协程，并在 Windows 上使用 psycopg 支持的 Selector 事件循环。"""
    loop_factory = None
    if sys.platform == "win32":
        # Windows 默认 ProactorEventLoop；psycopg 的异步连接明确不支持它。
        loop_factory = _new_windows_selector_loop

    with asyncio.Runner(loop_factory=loop_factory) as runner:
        return runner.run(coroutine)
