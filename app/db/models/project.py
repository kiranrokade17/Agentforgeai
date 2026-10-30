import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.architecture_plan import ArchitecturePlan
    from app.db.models.specification import Specification
    from app.db.models.task import Task
    from app.db.models.workspace import Workspace


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "projects"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    stack_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="projects")
    specifications: Mapped[list["Specification"]] = relationship(
        "Specification",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Specification.version",
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="project", cascade="all, delete-orphan", order_by="Task.order"
    )
    architecture_plans: Mapped[list["ArchitecturePlan"]] = relationship(
        "ArchitecturePlan", back_populates="project", cascade="all, delete-orphan"
    )
