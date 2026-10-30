"""Phase 3 – Tasks, task dependencies, and architecture plans

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-30
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002_add_specifications_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── architecture_plans ───────────────────────────────────────────────────
    op.create_table(
        "architecture_plans",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "specification_id",
            sa.Uuid(),
            sa.ForeignKey("specifications.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # ── tasks ────────────────────────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "specification_id",
            sa.Uuid(),
            sa.ForeignKey("specifications.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("task_type", sa.String(50), nullable=False, server_default="backend"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(50), nullable=False, server_default="backlog"),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=False),
        sa.Column("required_tests", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "task_type IN ('frontend','backend','database','testing','documentation','devops')",
            name="ck_task_type",
        ),
        sa.CheckConstraint(
            "priority IN ('critical','high','medium','low')", name="ck_task_priority"
        ),
        sa.CheckConstraint(
            "status IN ('backlog','in_progress','done','blocked','cancelled')",
            name="ck_task_status",
        ),
    )

    # ── task_dependencies ────────────────────────────────────────────────────
    op.create_table(
        "task_dependencies",
        sa.Column(
            "task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "depends_on_task_id",
            sa.Uuid(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependency"),
    )


def downgrade() -> None:
    op.drop_table("task_dependencies")
    op.drop_table("tasks")
    op.drop_table("architecture_plans")
