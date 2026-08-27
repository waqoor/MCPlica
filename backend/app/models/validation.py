from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.validation import ValidationStatus
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [value.value for value in enum_type]


class ValidationReport(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "validation_reports"
    __table_args__ = (
        CheckConstraint(
            "operation_source_count >= 0 AND operation_excluded_count >= 0 AND "
            "operation_expected_count >= 0 AND operation_generated_count >= 0",
            name="ck_validation_reports_counts_nonnegative",
        ),
        CheckConstraint(
            "coverage_percent >= 0 AND coverage_percent <= 100",
            name="ck_validation_reports_coverage_range",
        ),
        CheckConstraint(
            "blocking_error_count >= 0 AND warning_count >= 0",
            name="ck_validation_reports_findings_nonnegative",
        ),
        CheckConstraint(
            "operation_excluded_count <= operation_source_count AND "
            "operation_expected_count = operation_source_count - operation_excluded_count",
            name="ck_validation_reports_count_consistency",
        ),
        CheckConstraint(
            "overall_status <> 'pass'::validation_status OR ("
            "blocking_error_count = 0 AND "
            "operation_generated_count = operation_expected_count "
            "AND coverage_percent = 100)",
            name="ck_validation_reports_pass_integrity",
        ),
    )

    build_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("builds.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    overall_status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, name="validation_status", values_callable=_enum_values),
        nullable=False,
    )
    operation_source_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    operation_excluded_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    operation_expected_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    operation_generated_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    coverage_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    blocking_error_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    report_json: Mapped[dict[str, object]] = mapped_column(JSONB(), nullable=False)


class OperationExclusion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "operation_exclusions"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "operation_key",
            name="uq_operation_exclusions_project_operation",
        ),
        CheckConstraint(
            "char_length(btrim(reason)) > 0",
            name="ck_operation_exclusions_reason_nonempty",
        ),
        CheckConstraint(
            "char_length(btrim(reason_code)) > 0",
            name="ck_operation_exclusions_reason_code_nonempty",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    build_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("builds.id", ondelete="SET NULL"),
        nullable=True,
    )
    operation_key: Mapped[str] = mapped_column(String(160), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(Text(), nullable=False)
    is_user_requested: Mapped[bool] = mapped_column(Boolean(), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
