import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.architecture_plan import ArchitecturePlan
    from app.db.models.project import Project
    from app.db.models.task import Task
    from app.db.models.user import User


class Specification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "specifications"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_spec_project_version"),
        CheckConstraint(
            "status IN ('draft','in_review','approved','rejected')", name="ck_specification_status"
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="draft", nullable=False
    )  # draft, in_review, approved, rejected
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="specifications")
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by])
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="specification", cascade="all, delete-orphan"
    )
    architecture_plans: Mapped[list["ArchitecturePlan"]] = relationship(
        "ArchitecturePlan", back_populates="specification", cascade="all, delete-orphan"
    )
