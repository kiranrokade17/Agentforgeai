import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.task import Task


class TestRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "test_runs"

    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    command: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    exit_code: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CodeReview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "code_reviews"

    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    findings: Mapped[list["QualityFinding"]] = relationship(
        "QualityFinding",
        back_populates="review",
        cascade="all, delete-orphan",
    )


class QualityFinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quality_findings"

    review_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("code_reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    file: Mapped[str | None] = mapped_column(String(200), nullable=True)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    review: Mapped["CodeReview"] = relationship("CodeReview", back_populates="findings")
