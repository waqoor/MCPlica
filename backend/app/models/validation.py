from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.validation import ValidationStatus
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [value.value for value in enum_type]


class ValidationReport(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "validation_reports"

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
