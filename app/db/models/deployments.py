import uuid

from sqlalchemy import JSON, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Deployment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deployments"

    environment: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DeploymentStatusRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deployment_status_records"

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    conclusion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    run_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


class UsageRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "usage_records"

    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(default=1, nullable=False)
    cost_estimate: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
