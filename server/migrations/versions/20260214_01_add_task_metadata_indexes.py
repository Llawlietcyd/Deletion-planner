"""add task metadata and indexes

Revision ID: 20260214_01
Revises:
Create Date: 2026-02-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260214_01"
down_revision = None
branch_labels = None
depends_on = None


def _safe_add_column(table, column):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table)]
    if column.name not in columns:
        op.add_column(table, column)


def _safe_create_index(index_name, table_name, columns):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = [i["name"] for i in inspector.get_indexes(table_name)]
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns)


def upgrade():
    _safe_add_column("tasks", sa.Column("source", sa.String(length=20), nullable=True, server_default="manual"))
    _safe_add_column("tasks", sa.Column("decision_reason", sa.Text(), nullable=True, server_default=""))
    _safe_add_column("tasks", sa.Column("completed_at", sa.DateTime(), nullable=True))
    _safe_add_column("tasks", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    _safe_add_column("tasks", sa.Column("sort_order", sa.Integer(), nullable=True, server_default="0"))

    _safe_create_index("idx_tasks_status", "tasks", ["status"])
    _safe_create_index("idx_tasks_created_at", "tasks", ["created_at"])
    _safe_create_index("idx_tasks_sort_order", "tasks", ["sort_order"])
    _safe_create_index("idx_daily_plans_date", "daily_plans", ["date"])
    _safe_create_index("idx_task_history_date", "task_history", ["date"])


def downgrade():
    op.drop_index("idx_task_history_date", table_name="task_history")
    op.drop_index("idx_daily_plans_date", table_name="daily_plans")
    op.drop_index("idx_tasks_created_at", table_name="tasks")
    op.drop_index("idx_tasks_sort_order", table_name="tasks")
    op.drop_index("idx_tasks_status", table_name="tasks")
    op.drop_column("tasks", "deleted_at")
    op.drop_column("tasks", "completed_at")
    op.drop_column("tasks", "sort_order")
    op.drop_column("tasks", "decision_reason")
    op.drop_column("tasks", "source")
