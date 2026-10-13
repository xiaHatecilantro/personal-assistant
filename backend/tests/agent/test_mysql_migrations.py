"""在显式隔离的 MySQL 内创建一次性数据库，验证真实迁移往返。"""

import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


@pytest.mark.parametrize("option", ["database", "db", "init_command", "host"])
def test_migration_url_rejects_driver_overrides_before_any_connection(monkeypatch, option):
    monkeypatch.setenv(
        "MYSQL_TEST_DATABASE_URL",
        f"mysql+pymysql://root:test@127.0.0.1:13307/m10_acceptance?{option}=m10_acceptance",
    )

    def forbidden_connection(*_args, **_kwargs):
        raise AssertionError("unsafe URL must be rejected before creating any engine")

    monkeypatch.setattr(sys.modules[__name__], "create_engine", forbidden_connection)
    with pytest.raises(pytest.fail.Exception, match="unsafe connection query parameter"):
        test_mysql_migrations_round_trip_without_foreign_key_index_errors()


@pytest.mark.integration
def test_mysql_migrations_round_trip_without_foreign_key_index_errors():
    configured = os.getenv("MYSQL_TEST_DATABASE_URL")
    if not configured:
        pytest.skip("MYSQL_TEST_DATABASE_URL is not configured")
    url = make_url(configured)
    if url.drivername != "mysql+pymysql" or url.database != "m10_acceptance":
        pytest.fail("migration tests require the isolated m10_acceptance database")
    # PyMySQL 的 query 参数可覆盖 URL 路径中的库名，甚至在连接时执行 USE；
    # 迁移包含 DROP TABLE，连接选项必须使用窄白名单并在任何 DDL 前拒绝覆盖。
    if set(url.query) - {"charset", "ssl_disabled"}:
        pytest.fail("unsafe connection query parameter in migration test URL")
    engine = create_engine(url)
    # 数据库名仅由固定前缀和服务器生成的 UUID 构成，不能来自请求或环境输入。
    database = "m10_acceptance_migration_" + uuid4().hex
    created = False
    migrated = None
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT DATABASE()")) == "m10_acceptance"
            connection.execute(text(f"CREATE DATABASE `{database}`"))
            created = True
        migration_url = url.set(database=database)
        migrated = create_engine(migration_url)
        with migrated.connect() as connection:
            assert connection.scalar(text("SELECT DATABASE()")) == database
        environment = {
            **os.environ,
            "APP_ENV": "test",
            "DATABASE_URL": migration_url.render_as_string(hide_password=False),
        }
        # 既验证 base 往返，也验证兼容性索引保留后升级不会重复创建索引。
        for command in (
            "upgrade head", "downgrade 0003_agent_runtime", "upgrade head",
            "downgrade base", "upgrade head",
        ):
            result = subprocess.run(
                [sys.executable, "-m", "alembic", *command.split()],
                cwd=Path(__file__).resolve().parents[2],
                env=environment, capture_output=True, text=True, timeout=90,
            )
            assert result.returncode == 0, result.stderr
        with migrated.connect() as connection:
            assert connection.scalar(text("SELECT DATABASE()")) == database
            tables = set(inspect(connection).get_table_names())
            assert {"users", "tasks", "notes", "raw_sources", "agent_runs"} <= tables
            for table in ("tasks", "notes", "raw_sources"):
                indexes = inspect(connection).get_indexes(table)
                assert any(index["column_names"] == ["owner_id"] for index in indexes)
    finally:
        if migrated is not None:
            migrated.dispose()
        # 仅删除本用例成功创建的 UUID 库；不删除 URL 指定的库或其他验收数据。
        if created:
            with engine.connect() as connection:
                assert connection.scalar(text("SELECT DATABASE()")) == "m10_acceptance"
                connection.execute(text(f"DROP DATABASE `{database}`"))
        engine.dispose()
