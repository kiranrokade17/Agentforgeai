import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RepositoryRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repositories"

    owner: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), nullable=False, default="main")
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="github")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="connected")

    pull_requests: Mapped[list["PullRequestRecord"]] = relationship(
        "PullRequestRecord",
        back_populates="repository",
        cascade="all, delete-orphan",
    )


class PullRequestRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pull_requests"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    head_branch: Mapped[str] = mapped_column(String(200), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")

    repository: Mapped["RepositoryRecord"] = relationship("RepositoryRecord", back_populates="pull_requests")
