"""Keep foreign-key support indexes independent from historical query indexes.

Revision ID: 0004_mysql_fk_indexes
Revises: 0003_agent_runtime
Create Date: 2026-10-12
"""

from alembic import context, op
import sqlalchemy as sa


revision = "0004_mysql_fk_indexes"
down_revision = "0003_agent_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # InnoDB 可用复合查询索引替代自动外键索引；0002 回滚先删除查询索引，
    # 因而必须预留独立的 owner_id 索引，不能改写已发布的 0002。
    for table in ("tasks", "notes", "raw_sources"):
        name = f"ix_{table}_owner_fk"
        existing = (
            set() if context.is_offline_mode()
            else {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}
        )
        if name not in existing:
            op.create_index(name, table, ["owner_id"])


def downgrade() -> None:
    # 兼容性修复刻意保留这三个非唯一索引，否则继续回退 0002 会再次失败。
    # 回退到 base 时随业务表删除；回到 0003 再升级时 upgrade 幂等复用它们。
    pass
