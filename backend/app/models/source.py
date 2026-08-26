from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.sources import SourceKind, SourceOrigin
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [value.value for value in enum_type]


class ProjectSource(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "project_sources"
    __table_args__ = (
        Index(
            "uq_project_sources_primary_executable",
            "project_id",
            unique=True,
            postgresql_where=text(
                "is_primary AND kind IN ('openapi'::source_kind, 'api_inventory'::source_kind)"
            ),
        ),
        Index("ix_project_sources_project_created", "project_id", "created_at"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[SourceKind] = mapped_column(
        Enum(
            SourceKind,
            name="source_kind",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    origin_type: Mapped[SourceOrigin] = mapped_column(
        Enum(
            SourceOrigin,
            name="source_origin",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    source_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean(), default=False, nullable=False)


class SourceVersion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "source_versions"
    __table_args__ = (
        UniqueConstraint("source_id", "content_sha256", name="uq_source_versions_source_hash"),
        Index("ix_source_versions_source_created", "source_id", "created_at"),
    )

    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("project_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    media_type: Mapped[str] = mapped_column(String(200), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text(), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    detected_format: Mapped[str] = mapped_column(String(80), nullable=False)
    source_etag: Mapped[str | None] = mapped_column(Text(), nullable=True)
    source_last_modified: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
