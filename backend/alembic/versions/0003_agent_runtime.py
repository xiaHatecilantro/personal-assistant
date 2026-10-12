"""Add agent runtime audit tables.

Revision ID: 0003_agent_runtime
Revises: 0002_integrity_constraints
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_agent_runtime"
down_revision = "0002_integrity_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("thread_id", sa.String(length=36), nullable=False),
        sa.Column("graph_version", sa.String(length=50), nullable=False),
        sa.Column("max_steps", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("step_count", sa.Integer(), nullable=False),
        sa.Column("final_answer", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thread_id"),
    )
    op.create_index(
        "ix_agent_runs_owner_created",
        "agent_runs",
        ["owner_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_runs_owner_status",
        "agent_runs",
        ["owner_id", "status"],
        unique=False,
    )

    op.create_table(
        "agent_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_agent_events_run_sequence"),
    )

    op.create_table(
        "agent_approvals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("tool_call_id", sa.String(length=128), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("tool_version", sa.String(length=50), nullable=False),
        sa.Column("arguments_json", sa.JSON(), nullable=False),
        sa.Column("arguments_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=True),
        sa.Column("decision_payload", sa.JSON(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "tool_call_id",
            name="uq_agent_approvals_run_tool_call",
        ),
    )

    op.create_table(
        "agent_tool_executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("tool_call_id", sa.String(length=128), nullable=False),
        sa.Column("arguments_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("business_entity_type", sa.String(length=100), nullable=True),
        sa.Column("business_entity_id", sa.String(length=100), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "tool_call_id",
            name="uq_agent_tool_executions_run_tool_call",
        ),
    )


def downgrade() -> None:
    op.drop_table("agent_tool_executions")
    op.drop_table("agent_approvals")
    op.drop_table("agent_events")
    op.drop_table("agent_runs")
