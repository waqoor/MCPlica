from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.builds import BuildStatus, BuildTrigger
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [value.value for value in enum_type]


class Build(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "builds"
    __table_args__ = (
        UniqueConstraint("project_id", "sequence", name="uq_builds_sequence"),
        Index("ix_builds_project_created", "project_id", "created_at"),
        Index("ix_builds_status_created", "status", "created_at"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer(), nullable=False)
    status: Mapped[BuildStatus] = mapped_column(
        Enum(BuildStatus, name="build_status", values_callable=_enum_values),
        nullable=False,
    )
    trigger: Mapped[BuildTrigger] = mapped_column(
        Enum(BuildTrigger, name="build_trigger", values_callable=_enum_values),
        nullable=False,
    )
    canonical_snapshot_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("canonical_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
    )
    previous_build_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("builds.id", ondelete="SET NULL"),
        nullable=True,
    )
    compiler_version: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    runtime_compatibility: Mapped[str] = mapped_column(String(80), nullable=False)
    analysis_model: Mapped[str | None] = mapped_column(String(300), nullable=True)
    validation_model: Mapped[str | None] = mapped_column(String(300), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(300), nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    prompt_bundle_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    build_config_json: Mapped[dict[str, object]] = mapped_column(JSONB(), nullable=False)
    enrichment_json: Mapped[dict[str, object] | None] = mapped_column(JSONB(), nullable=True)
    enrichment_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manifest_storage_key: Mapped[str | None] = mapped_column(Text(), nullable=True)
    artifact_storage_key: Mapped[str | None] = mapped_column(Text(), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    requested_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BuildSourceVersion(Base):
    __tablename__ = "build_source_versions"

    build_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("builds.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_versions.id", ondelete="RESTRICT"),
        primary_key=True,
    )


class BuildAIRun(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "build_ai_runs"
    __table_args__ = (
        UniqueConstraint("build_id", "run_key", name="uq_build_ai_runs_build_run_key"),
        Index("ix_build_ai_runs_build_created", "build_id", "created_at"),
    )

    build_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("builds.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_key: Mapped[str] = mapped_column(String(160), nullable=False)
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    operation_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(300), nullable=False)
    prompt_template_id: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_template_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_context_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(JSONB(), nullable=False)
    response_schema_id: Mapped[str] = mapped_column(String(160), nullable=False)
    response_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_json: Mapped[dict[str, object] | None] = mapped_column(JSONB(), nullable=True)
    usage_json: Mapped[dict[str, object] | None] = mapped_column(JSONB(), nullable=True)
    cost_json: Mapped[dict[str, object] | None] = mapped_column(JSONB(), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
