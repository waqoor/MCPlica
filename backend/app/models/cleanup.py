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
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.cleanup import (
    CleanupJobKind,
    CleanupJobStatus,
    CleanupTargetStatus,
    CleanupTargetType,
)
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [value.value for value in enum_type]


class CleanupJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cleanup_jobs"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(idempotency_key)) > 0",
            name="ck_cleanup_jobs_idempotency_key_nonempty",
        ),
        CheckConstraint(
            "total_targets >= 0 AND completed_targets >= 0 AND skipped_targets >= 0 "
            "AND failed_targets >= 0 AND completed_targets + skipped_targets + "
            "failed_targets <= total_targets",
            name="ck_cleanup_jobs_progress",
        ),
        Index("ix_cleanup_jobs_project_created", "project_id", "created_at"),
        Index("ix_cleanup_jobs_status_created", "status", "created_at"),
    )

    kind: Mapped[CleanupJobKind] = mapped_column(
        Enum(CleanupJobKind, name="cleanup_job_kind", values_callable=_enum_values),
        nullable=False,
    )
    status: Mapped[CleanupJobStatus] = mapped_column(
        Enum(CleanupJobStatus, name="cleanup_job_status", values_callable=_enum_values),
        default=CleanupJobStatus.PENDING,
        nullable=False,
    )
    project_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    requested_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    total_targets: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    completed_targets: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    skipped_targets: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    failed_targets: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CleanupTarget(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cleanup_targets"
    __table_args__ = (
        UniqueConstraint("job_id", "target_key", name="uq_cleanup_targets_job_target_key"),
        CheckConstraint("attempt_count >= 0", name="ck_cleanup_targets_attempt_count"),
        CheckConstraint(
            "(status = 'running'::cleanup_target_status AND execution_token IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR "
            "(status <> 'running'::cleanup_target_status AND execution_token IS NULL "
            "AND lease_expires_at IS NULL)",
            name="ck_cleanup_targets_execution_owner_shape",
        ),
        CheckConstraint(
            "(target_type = 'object'::cleanup_target_type AND storage_key IS NOT NULL "
            "AND collection_name IS NULL AND vector_project_id IS NULL "
            "AND generation_id IS NULL) OR "
            "(target_type = 'vector_generation'::cleanup_target_type "
            "AND storage_key IS NULL AND collection_name IS NOT NULL "
            "AND vector_project_id IS NOT NULL AND generation_id IS NOT NULL)",
            name="ck_cleanup_targets_shape",
        ),
        Index(
            "ix_cleanup_targets_due",
            "next_attempt_at",
            "created_at",
            postgresql_where=text(
                "status IN ('pending'::cleanup_target_status, "
                "'running'::cleanup_target_status, 'retrying'::cleanup_target_status)"
            ),
        ),
        Index("ix_cleanup_targets_job_status", "job_id", "status"),
    )

    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("cleanup_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_key: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[CleanupTargetType] = mapped_column(
        Enum(CleanupTargetType, name="cleanup_target_type", values_callable=_enum_values),
        nullable=False,
    )
    status: Mapped[CleanupTargetStatus] = mapped_column(
        Enum(
            CleanupTargetStatus,
            name="cleanup_target_status",
            values_callable=_enum_values,
        ),
        default=CleanupTargetStatus.PENDING,
        nullable=False,
    )
    storage_key: Mapped[str | None] = mapped_column(Text(), nullable=True)
    collection_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vector_project_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    generation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_token: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
