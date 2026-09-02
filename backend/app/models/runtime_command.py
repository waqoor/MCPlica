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
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.deployments import RuntimeCommandAction, RuntimeCommandStatus
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [value.value for value in enum_type]


class RuntimeLifecycleCommand(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "runtime_lifecycle_commands"
    __table_args__ = (
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_runtime_lifecycle_commands_attempt_count",
        ),
        CheckConstraint(
            "char_length(btrim(reason)) > 0 AND char_length(btrim(idempotency_key)) > 0",
            name="ck_runtime_lifecycle_commands_identity_nonempty",
        ),
        CheckConstraint(
            "(subject_type IS NULL) = (subject_id IS NULL)",
            name="ck_runtime_lifecycle_commands_subject_pair",
        ),
        CheckConstraint(
            "(status = 'effective'::runtime_command_status AND effective_at IS NOT NULL "
            "AND failed_at IS NULL) OR "
            "(status = 'failed'::runtime_command_status AND failed_at IS NOT NULL "
            "AND last_error_code IS NOT NULL) OR "
            "status IN ('pending'::runtime_command_status, "
            "'dispatched'::runtime_command_status, 'running'::runtime_command_status)",
            name="ck_runtime_lifecycle_commands_status_shape",
        ),
        CheckConstraint(
            "(status IN ('dispatched'::runtime_command_status, "
            "'running'::runtime_command_status) AND execution_token IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR "
            "(status IN ('pending'::runtime_command_status, "
            "'failed'::runtime_command_status, 'effective'::runtime_command_status) "
            "AND execution_token IS NULL AND lease_expires_at IS NULL)",
            name="ck_runtime_lifecycle_commands_execution_owner_shape",
        ),
        Index(
            "ix_runtime_commands_dispatch_due",
            "next_attempt_at",
            "created_at",
            postgresql_where=text(
                "status IN ('pending'::runtime_command_status, "
                "'dispatched'::runtime_command_status, 'running'::runtime_command_status, "
                "'failed'::runtime_command_status)"
            ),
        ),
        Index(
            "ix_runtime_commands_project_created",
            "project_id",
            "created_at",
        ),
        Index(
            "ix_runtime_commands_subject_created",
            "subject_type",
            "subject_id",
            "sequence",
        ),
        Index("ix_runtime_commands_transition", "transition_id"),
        UniqueConstraint("sequence", name="uq_runtime_lifecycle_commands_sequence"),
    )

    sequence: Mapped[int] = mapped_column(BigInteger(), Identity(start=1), nullable=False)

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    deployment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
    )
    build_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("builds.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transition_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action: Mapped[RuntimeCommandAction] = mapped_column(
        Enum(
            RuntimeCommandAction,
            name="runtime_command_action",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    status: Mapped[RuntimeCommandStatus] = mapped_column(
        Enum(
            RuntimeCommandStatus,
            name="runtime_command_status",
            values_callable=_enum_values,
        ),
        default=RuntimeCommandStatus.PENDING,
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(160), nullable=False)
    subject_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    requested_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    retryable: Mapped[bool] = mapped_column(Boolean(), default=True, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_token: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
