from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
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

from app.domain.builds import BuildStatus, BuildTrigger
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [value.value for value in enum_type]


class Build(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "builds"
    __table_args__ = (
        UniqueConstraint("project_id", "sequence", name="uq_builds_sequence"),
        CheckConstraint("sequence > 0", name="ck_builds_sequence_positive"),
        CheckConstraint(
            "embedding_dimensions IS NULL OR embedding_dimensions >= 0",
            name="ck_builds_embedding_dimensions",
        ),
        CheckConstraint(
            "jsonb_typeof(build_config_json) = 'object'",
            name="ck_builds_config_object",
        ),
        CheckConstraint(
            "enrichment_sha256 IS NULL OR enrichment_sha256 ~ '^[a-f0-9]{64}$'",
            name="ck_builds_enrichment_sha256",
        ),
        CheckConstraint(
            "manifest_sha256 IS NULL OR manifest_sha256 ~ '^[a-f0-9]{64}$'",
            name="ck_builds_manifest_sha256",
        ),
        CheckConstraint(
            "artifact_sha256 IS NULL OR artifact_sha256 ~ '^[a-f0-9]{64}$'",
            name="ck_builds_artifact_sha256",
        ),
        CheckConstraint(
            "(status IN ('READY'::build_status, 'FAILED'::build_status, "
            "'CANCELLED'::build_status)) = (completed_at IS NOT NULL)",
            name="ck_builds_terminal_completion",
        ),
        CheckConstraint(
            "status <> 'READY'::build_status OR ("
            "canonical_snapshot_id IS NOT NULL AND enrichment_json IS NOT NULL "
            "AND enrichment_sha256 IS NOT NULL AND manifest_sha256 IS NOT NULL "
            "AND manifest_storage_key IS NOT NULL AND artifact_sha256 IS NOT NULL "
            "AND artifact_storage_key IS NOT NULL AND analysis_model IS NOT NULL "
            "AND validation_model IS NOT NULL AND prompt_bundle_version IS NOT NULL "
            "AND error_code IS NULL AND error_summary IS NULL)",
            name="ck_builds_ready_complete",
        ),
        CheckConstraint(
            "status <> 'FAILED'::build_status OR error_code IS NOT NULL",
            name="ck_builds_failed_error",
        ),
        CheckConstraint(
            "cancellation_acknowledged_at IS NULL OR "
            "(cancellation_requested_at IS NOT NULL AND status = 'CANCELLED'::build_status)",
            name="ck_builds_cancellation_acknowledgement",
        ),
        CheckConstraint(
            "status <> 'CANCELLED'::build_status OR cancellation_acknowledged_at IS NOT NULL",
            name="ck_builds_cancelled_acknowledged",
        ),
        CheckConstraint(
            "(admission_token IS NULL) = (admission_lease_expires_at IS NULL)",
            name="ck_builds_admission_lease_token",
        ),
        CheckConstraint(
            "admission_token IS NULL OR admission_acquired_at IS NOT NULL",
            name="ck_builds_admission_acquired",
        ),
        CheckConstraint(
            "admission_attempt_count >= 0",
            name="ck_builds_admission_attempt_count",
        ),
        CheckConstraint(
            "pipeline_stage IS NULL OR pipeline_stage NOT IN "
            "('FAILED'::build_status, 'CANCELLED'::build_status)",
            name="ck_builds_pipeline_stage",
        ),
        Index("ix_builds_project_created", "project_id", "created_at"),
        Index("ix_builds_status_created", "status", "created_at"),
        Index(
            "uq_builds_one_active_per_project",
            "project_id",
            unique=True,
            postgresql_where=text(
                "status NOT IN ('READY'::build_status, 'FAILED'::build_status, "
                "'CANCELLED'::build_status)"
            ),
        ),
        Index(
            "ix_builds_cancellation_requested",
            "cancellation_requested_at",
            postgresql_where=text(
                "cancellation_requested_at IS NOT NULL AND cancellation_acknowledged_at IS NULL"
            ),
        ),
        Index(
            "ix_builds_admission_active",
            "admission_lease_expires_at",
            postgresql_where=text("admission_token IS NOT NULL"),
        ),
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
    pipeline_stage: Mapped[BuildStatus | None] = mapped_column(
        Enum(BuildStatus, name="build_status", values_callable=_enum_values),
        nullable=True,
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
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancellation_requested_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    cancellation_acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    admission_token: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    admission_acquired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    admission_enqueued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    admission_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    admission_lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    admission_released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    admission_attempt_count: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default="0"
    )


class BuildSourceVersion(Base):
    __tablename__ = "build_source_versions"
    __table_args__ = (Index("ix_build_source_versions_source_version_id", "source_version_id"),)

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
        CheckConstraint(
            "status IN ('succeeded', 'failed')",
            name="ck_build_ai_runs_status",
        ),
        CheckConstraint(
            "input_context_sha256 ~ '^[a-f0-9]{64}$'",
            name="ck_build_ai_runs_input_hash",
        ),
        CheckConstraint(
            "response_sha256 IS NULL OR response_sha256 ~ '^[a-f0-9]{64}$'",
            name="ck_build_ai_runs_response_hash",
        ),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_build_ai_runs_latency",
        ),
        CheckConstraint(
            "(status = 'succeeded' AND response_json IS NOT NULL "
            "AND response_sha256 IS NOT NULL AND error_code IS NULL) OR "
            "(status = 'failed' AND response_json IS NULL AND error_code IS NOT NULL)",
            name="ck_build_ai_runs_outcome",
        ),
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
