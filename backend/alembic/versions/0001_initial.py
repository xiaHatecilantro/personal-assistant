"""Initial schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("username"),
        )
    if "tasks" not in existing_tables:
        op.create_table(
            "tasks",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("priority", sa.Enum("high", "medium", "low", name="task_priority"), nullable=False),
            sa.Column("status", sa.Enum("todo", "in_progress", "done", name="task_status"), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("tag", sa.String(length=50), nullable=True),
            sa.Column(
                "task_type",
                sa.Enum("short_term", "long_term", "daily", name="task_type"),
                nullable=False,
            ),
            sa.Column(
                "deadline_precision",
                sa.Enum("day", "month", "year", name="deadline_precision"),
                nullable=True,
            ),
            sa.Column("timer_preset", sa.Integer(), nullable=True),
            sa.Column("timer_total_seconds", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if "notes" not in existing_tables:
        op.create_table(
            "notes",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("category", sa.String(length=50), nullable=True),
            sa.Column("tags", sa.Text(), nullable=True),
            sa.Column("wikilinks", sa.Text(), nullable=True),
            sa.Column("source_url", sa.String(length=500), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("domain", sa.String(length=50), nullable=True),
            sa.Column("is_pinned", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if "raw_sources" not in existing_tables:
        op.create_table(
            "raw_sources",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("source_url", sa.String(length=500), nullable=True),
            sa.Column("content_hash", sa.String(length=16), nullable=False),
            sa.Column("status", sa.Enum("pending", "ingested", name="raw_source_status"), nullable=False),
            sa.Column("ingested_to_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table_name in ("raw_sources", "notes", "tasks", "users"):
        if table_name in existing_tables:
            op.drop_table(table_name)
