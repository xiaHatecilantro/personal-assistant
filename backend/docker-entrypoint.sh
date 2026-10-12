#!/bin/sh
set -e

# MySQL 健康检查有明确超时，避免容器在数据库不可达时无限等待。
python - <<'PY'
import os
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

database_url = os.environ["DATABASE_URL"]
deadline = time.time() + 60

while True:
    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        break
    except OperationalError as exc:
        if time.time() >= deadline:
            raise exc
        print("Waiting for MySQL to accept connections...")
        time.sleep(2)
PY

# 业务表和 LangGraph Checkpoint 分属不同数据库，必须分别初始化后再接收流量。
alembic upgrade head
python -m app.agent.checkpoint
exec python -m app.server --host 0.0.0.0 --port 8000
