import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.project import Project
    from app.db.models.specification import Specification
    from app.db.models.user import User


class ArchitecturePlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "architecture_plans"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_architecture_plan_project_version"),
        CheckConstraint(
            "status IN ('draft','approved','rejected')",
            name="ck_architecture_plan_status",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    specification_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("specifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="architecture_plans")
    specification: Mapped["Specification"] = relationship(
        "Specification", back_populates="architecture_plans"
    )
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by])
