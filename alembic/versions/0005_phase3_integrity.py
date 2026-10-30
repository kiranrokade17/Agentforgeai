"""Phase 3 approval fields and integrity constraints

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-30
"""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "architecture_plans",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_architecture_plan_approved_by",
        "architecture_plans",
        "users",
        ["approved_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_architecture_plan_project_version",
        "architecture_plans",
        ["project_id", "version"],
    )
    op.create_check_constraint(
        "ck_architecture_plan_status",
        "architecture_plans",
        "status IN ('draft','approved','rejected')",
    )

    op.add_column("tasks", sa.Column("approved_by", sa.Uuid(), nullable=True))
    op.add_column("tasks", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_task_approved_by",
        "tasks",
        "users",
        ["approved_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_task_specification_order",
        "tasks",
        ["specification_id", "order"],
    )
    op.create_check_constraint("ck_task_order_positive", "tasks", '"order" >= 1')


def downgrade() -> None:
    op.drop_constraint("ck_task_order_positive", "tasks", type_="check")
    op.drop_constraint("uq_task_specification_order", "tasks", type_="unique")
    op.drop_constraint("fk_task_approved_by", "tasks", type_="foreignkey")
    op.drop_column("tasks", "approved_at")
    op.drop_column("tasks", "approved_by")

    op.drop_constraint("ck_architecture_plan_status", "architecture_plans", type_="check")
    op.drop_constraint(
        "uq_architecture_plan_project_version",
        "architecture_plans",
        type_="unique",
    )
    op.drop_constraint(
        "fk_architecture_plan_approved_by",
        "architecture_plans",
        type_="foreignkey",
    )
    op.drop_column("architecture_plans", "approved_at")
