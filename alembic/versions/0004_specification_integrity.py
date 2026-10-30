"""Add specification version uniqueness and status constraint

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-30
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_spec_project_version",
        "specifications",
        ["project_id", "version"],
    )
    op.create_check_constraint(
        "ck_specification_status",
        "specifications",
        "status IN ('draft','in_review','approved','rejected')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_specification_status", "specifications", type_="check")
    op.drop_constraint("uq_spec_project_version", "specifications", type_="unique")
