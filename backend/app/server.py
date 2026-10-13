"""使用 psycopg 兼容事件循环启动 Uvicorn。"""

import argparse

import uvicorn

from app.asyncio_compat import selector_event_loop_factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Personal Assistant API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        loop=selector_event_loop_factory,
    )


if __name__ == "__main__":
    main()
