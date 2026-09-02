from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.sources import SourceKind, SourceOrigin
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [value.value for value in enum_type]


class ProjectSource(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "project_sources"
    __table_args__ = (
        CheckConstraint(
            "(origin_type = 'url' AND source_url IS NOT NULL) OR "
            "(origin_type = 'upload' AND source_url IS NULL)",
            name="ck_project_sources_origin_url",
        ),
        CheckConstraint(
            "(current_version_id IS NULL AND current_version_selected_at IS NULL "
            "AND last_observed_at IS NULL AND last_observed_etag IS NULL "
            "AND last_observed_last_modified IS NULL) OR "
            "(current_version_id IS NOT NULL AND current_version_selected_at IS NOT NULL "
            "AND last_observed_at IS NOT NULL)",
            name="ck_project_sources_current_selection_shape",
        ),
        ForeignKeyConstraint(
            ["id", "current_version_id"],
            ["source_versions.source_id", "source_versions.id"],
            name="fk_project_sources_current_version_same_source",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        Index(
            "uq_project_sources_primary_executable",
            "project_id",
            unique=True,
            postgresql_where=text(
                "is_primary AND kind IN ('openapi'::source_kind, 'api_inventory'::source_kind)"
            ),
        ),
        Index("ix_project_sources_project_created", "project_id", "created_at"),
        Index("ix_project_sources_current_version_id", "current_version_id"),
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
    current_version_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    current_version_selected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_observed_etag: Mapped[str | None] = mapped_column(Text(), nullable=True)
    last_observed_last_modified: Mapped[str | None] = mapped_column(Text(), nullable=True)


class SourceVersion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "source_versions"
    __table_args__ = (
        UniqueConstraint("source_id", "content_sha256", name="uq_source_versions_source_hash"),
        UniqueConstraint("source_id", "id", name="uq_source_versions_source_id_id"),
        CheckConstraint("byte_size >= 0", name="ck_source_versions_byte_size"),
        CheckConstraint("byte_size > 0", name="ck_source_versions_nonempty"),
        CheckConstraint(
            "content_sha256 ~ '^[a-f0-9]{64}$'",
            name="ck_source_versions_sha256",
        ),
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


class SourceFinding(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "source_findings"
    __table_args__ = (
        UniqueConstraint(
            "build_id",
            "source_version_id",
            "finding_key",
            name="uq_source_findings_build_source_key",
        ),
        CheckConstraint(
            "severity IN ('error', 'warning', 'info')",
            name="ck_source_findings_severity",
        ),
        CheckConstraint(
            "char_length(btrim(stage)) > 0 AND char_length(btrim(code)) > 0 "
            "AND char_length(btrim(message)) > 0",
            name="ck_source_findings_required_text",
        ),
        CheckConstraint(
            "finding_key ~ '^[a-f0-9]{64}$'",
            name="ck_source_findings_key",
        ),
        CheckConstraint(
            "(line_number IS NULL OR line_number >= 1) "
            "AND (column_number IS NULL OR column_number >= 1)",
            name="ck_source_findings_position",
        ),
        Index("ix_source_findings_build", "build_id"),
        Index(
            "ix_source_findings_source_created",
            "source_version_id",
            "created_at",
        ),
    )

    build_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("builds.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    finding_key: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text(), nullable=False)
    pointer: Mapped[str | None] = mapped_column(Text(), nullable=True)
    line: Mapped[int | None] = mapped_column("line_number", Integer(), nullable=True)
    column: Mapped[int | None] = mapped_column("column_number", Integer(), nullable=True)
    details_json: Mapped[dict[str, object]] = mapped_column(
        "details",
        JSONB(),
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
