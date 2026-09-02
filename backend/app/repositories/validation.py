from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.validation import (
    OperationExclusionRecord,
    ValidationFinding,
    ValidationReportRecord,
    ValidationStatus,
)
from app.models.validation import OperationExclusion, ValidationReport
from app.repositories.build_execution import require_build_execution_owner


def _report_to_domain(model: ValidationReport) -> ValidationReportRecord:
    raw_findings = model.report_json.get("findings", [])
    findings = (
        [ValidationFinding.model_validate(item) for item in cast(list[object], raw_findings)]
        if isinstance(raw_findings, list)
        else []
    )
    return ValidationReportRecord(
        id=model.id,
        build_id=model.build_id,
        overall_status=model.overall_status,
        operation_source_count=model.operation_source_count,
        operation_excluded_count=model.operation_excluded_count,
        operation_expected_count=model.operation_expected_count,
        operation_generated_count=model.operation_generated_count,
        coverage_percent=float(model.coverage_percent),
        blocking_error_count=model.blocking_error_count,
        warning_count=model.warning_count,
        findings=findings,
        created_at=model.created_at,
    )


def _exclusion_to_domain(model: OperationExclusion) -> OperationExclusionRecord:
    return OperationExclusionRecord(
        id=model.id,
        project_id=model.project_id,
        build_id=model.build_id,
        operation_key=model.operation_key,
        reason_code=model.reason_code,
        reason=model.reason,
        is_user_requested=model.is_user_requested,
        created_by=model.created_by,
        created_at=model.created_at,
    )


class ValidationRepository:
    async def create_report(
        self,
        session: AsyncSession,
        *,
        build_id: UUID,
        overall_status: ValidationStatus,
        operation_source_count: int,
        operation_excluded_count: int,
        operation_expected_count: int,
        operation_generated_count: int,
        coverage_percent: float,
        blocking_error_count: int,
        warning_count: int,
        findings: list[ValidationFinding],
        admission_token: UUID,
    ) -> ValidationReportRecord:
        await require_build_execution_owner(
            session,
            build_id=build_id,
            admission_token=admission_token,
        )
        model = ValidationReport(
            build_id=build_id,
            overall_status=overall_status,
            operation_source_count=operation_source_count,
            operation_excluded_count=operation_excluded_count,
            operation_expected_count=operation_expected_count,
            operation_generated_count=operation_generated_count,
            coverage_percent=coverage_percent,
            blocking_error_count=blocking_error_count,
            warning_count=warning_count,
            report_json={
                "findings": [item.model_dump(mode="json", by_alias=True) for item in findings]
            },
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _report_to_domain(model)

    async def get_report(
        self,
        session: AsyncSession,
        build_id: UUID,
    ) -> ValidationReportRecord | None:
        model = await session.scalar(
            select(ValidationReport).where(ValidationReport.build_id == build_id)
        )
        return _report_to_domain(model) if model else None

    async def list_exclusions(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> list[OperationExclusionRecord]:
        result = await session.scalars(
            select(OperationExclusion)
            .where(OperationExclusion.project_id == project_id)
            .order_by(OperationExclusion.created_at.asc())
        )
        return [_exclusion_to_domain(model) for model in result]

    async def create_exclusion(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        build_id: UUID | None,
        operation_key: str,
        reason_code: str,
        reason: str,
        is_user_requested: bool,
        created_by: UUID,
    ) -> OperationExclusionRecord:
        model = OperationExclusion(
            project_id=project_id,
            build_id=build_id,
            operation_key=operation_key,
            reason_code=reason_code,
            reason=reason,
            is_user_requested=is_user_requested,
            created_by=created_by,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _exclusion_to_domain(model)

    async def get_exclusion(
        self,
        session: AsyncSession,
        exclusion_id: UUID,
    ) -> OperationExclusionRecord | None:
        model = await session.get(OperationExclusion, exclusion_id)
        return _exclusion_to_domain(model) if model else None

    async def delete_exclusion(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        exclusion_id: UUID,
    ) -> bool:
        result = cast(
            CursorResult[Any],
            await session.execute(
                delete(OperationExclusion).where(
                    OperationExclusion.id == exclusion_id,
                    OperationExclusion.project_id == project_id,
                )
            ),
        )
        return result.rowcount == 1
