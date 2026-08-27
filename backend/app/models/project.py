from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "jsonb_typeof(server_mappings) = 'object'",
            name="ck_projects_server_mappings_object",
        ),
        Index("ix_projects_active_build_id", "active_build_id"),
        Index("ix_projects_active_deployment_id", "active_deployment_id"),
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_server_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    server_mappings: Mapped[dict[str, str]] = mapped_column(
        JSONB(), default=dict, server_default="{}", nullable=False
    )
    mcp_hostname: Mapped[str] = mapped_column(String(253), nullable=False, unique=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    active_build_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "builds.id",
            name="fk_projects_active_build_id_builds",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
    )
    active_deployment_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "deployments.id",
            name="fk_projects_active_deployment_id_deployments",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
    )
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
