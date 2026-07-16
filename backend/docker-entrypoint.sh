#!/bin/sh
set -e

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

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
