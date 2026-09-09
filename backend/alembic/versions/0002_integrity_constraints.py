"""Add ownership constraints and query indexes.

Revision ID: 0002_integrity_constraints
Revises: 0001_initial
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_integrity_constraints"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _count(sql: str) -> int:
    return int(op.get_bind().execute(sa.text(sql)).scalar() or 0)


def _assert_clean_data() -> None:
    checks = {
        "tasks.owner_id 存在孤儿记录": (
            "SELECT COUNT(*) FROM tasks t LEFT JOIN users u ON u.id=t.owner_id "
            "WHERE u.id IS NULL"
        ),
        "tasks.parent_id 存在孤儿记录": (
            "SELECT COUNT(*) FROM tasks t LEFT JOIN tasks p ON p.id=t.parent_id "
            "WHERE t.parent_id IS NOT NULL AND p.id IS NULL"
        ),
        "notes.owner_id 存在孤儿记录": (
            "SELECT COUNT(*) FROM notes n LEFT JOIN users u ON u.id=n.owner_id "
            "WHERE u.id IS NULL"
        ),
        "raw_sources.owner_id 存在孤儿记录": (
            "SELECT COUNT(*) FROM raw_sources r LEFT JOIN users u ON u.id=r.owner_id "
            "WHERE u.id IS NULL"
        ),
        "raw_sources.ingested_to_id 存在孤儿记录": (
            "SELECT COUNT(*) FROM raw_sources r LEFT JOIN notes n ON n.id=r.ingested_to_id "
            "WHERE r.ingested_to_id IS NOT NULL AND n.id IS NULL"
        ),
        "raw_sources 存在重复 owner_id/content_hash": (
            "SELECT COUNT(*) FROM (SELECT 1 FROM raw_sources "
            "GROUP BY owner_id, content_hash HAVING COUNT(*) > 1) duplicates"
        ),
        "tasks.timer_total_seconds 存在负数": (
            "SELECT COUNT(*) FROM tasks WHERE timer_total_seconds < 0"
        ),
        "tasks.timer_preset 存在越界值": (
            "SELECT COUNT(*) FROM tasks WHERE timer_preset IS NOT NULL "
            "AND (timer_preset < 60 OR timer_preset > 7200)"
        ),
        "notes.confidence 存在越界值": (
            "SELECT COUNT(*) FROM notes WHERE confidence IS NOT NULL "
            "AND (confidence < 0 OR confidence > 1)"
        ),
    }
    failures = []
    for name, sql in checks.items():
        count = _count(sql)
        if count:
            failures.append(f"{name}（{count} 条）")
    if failures:
        raise RuntimeError("无法添加数据库约束，请先修复历史数据：" + "；".join(failures))


def upgrade() -> None:
    _assert_clean_data()

    op.alter_column(
        "notes", "is_pinned", existing_type=sa.Integer(), type_=sa.Boolean(), existing_nullable=False
    )
    op.create_foreign_key("fk_tasks_owner", "tasks", "users", ["owner_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_tasks_parent", "tasks", "tasks", ["parent_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_notes_owner", "notes", "users", ["owner_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_raw_sources_owner", "raw_sources", "users", ["owner_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key(
        "fk_raw_sources_note", "raw_sources", "notes", ["ingested_to_id"], ["id"], ondelete="SET NULL"
    )
    op.create_unique_constraint("uq_raw_sources_owner_hash", "raw_sources", ["owner_id", "content_hash"])
    op.create_check_constraint("ck_tasks_timer_total_nonnegative", "tasks", "timer_total_seconds >= 0")
    op.create_check_constraint(
        "ck_tasks_timer_preset_range",
        "tasks",
        "timer_preset IS NULL OR (timer_preset >= 60 AND timer_preset <= 7200)",
    )
    op.create_check_constraint(
        "ck_notes_confidence_range",
        "notes",
        "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
    )
    op.create_index("ix_tasks_owner_parent_created", "tasks", ["owner_id", "parent_id", "created_at"])
    op.create_index("ix_tasks_owner_status", "tasks", ["owner_id", "status"])
    op.create_index("ix_notes_owner_updated", "notes", ["owner_id", "updated_at"])
    op.create_index("ix_notes_owner_category", "notes", ["owner_id", "category"])
    op.create_index("ix_notes_owner_domain", "notes", ["owner_id", "domain"])
    op.create_index("ix_raw_sources_owner_status", "raw_sources", ["owner_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_raw_sources_owner_status", table_name="raw_sources")
    op.drop_index("ix_notes_owner_domain", table_name="notes")
    op.drop_index("ix_notes_owner_category", table_name="notes")
    op.drop_index("ix_notes_owner_updated", table_name="notes")
    op.drop_index("ix_tasks_owner_status", table_name="tasks")
    op.drop_index("ix_tasks_owner_parent_created", table_name="tasks")
    op.drop_constraint("ck_notes_confidence_range", "notes", type_="check")
    op.drop_constraint("ck_tasks_timer_preset_range", "tasks", type_="check")
    op.drop_constraint("ck_tasks_timer_total_nonnegative", "tasks", type_="check")
    op.drop_constraint("uq_raw_sources_owner_hash", "raw_sources", type_="unique")
    op.drop_constraint("fk_raw_sources_note", "raw_sources", type_="foreignkey")
    op.drop_constraint("fk_raw_sources_owner", "raw_sources", type_="foreignkey")
    op.drop_constraint("fk_notes_owner", "notes", type_="foreignkey")
    op.drop_constraint("fk_tasks_parent", "tasks", type_="foreignkey")
    op.drop_constraint("fk_tasks_owner", "tasks", type_="foreignkey")
    op.alter_column(
        "notes", "is_pinned", existing_type=sa.Boolean(), type_=sa.Integer(), existing_nullable=False
    )
