import hashlib
from collections.abc import Awaitable, Callable

from mcp_contracts import CanonicalApi, MCPManifest

from app.clients.database import DatabaseClient
from app.clients.mcp import MCPValidationClient
from app.core.exceptions import ProtocolValidationError
from app.domain.analysis import SemanticReviewFinding
from app.domain.builds import BuildConfiguration, BuildRecord
from app.domain.validation import (
    FindingSeverity,
    ValidationFinding,
    ValidationReportRecord,
    ValidationStatus,
)
from app.repositories.validation import ValidationRepository
from app.services.analysis.review import SemanticReviewService
from app.validators.build import (
    coverage_percent,
    validate_build,
    validate_runtime_manifest_size,
)


class ValidationService:
    def __init__(
        self,
        database: DatabaseClient,
        reports: ValidationRepository,
        semantic_review: SemanticReviewService,
        mcp: MCPValidationClient,
        *,
        runtime_version: str,
    ) -> None:
        self._database = database
        self._reports = reports
        self._semantic_review = semantic_review
        self._mcp = mcp
        self._runtime_version = runtime_version

    async def validate(
        self,
        *,
        build: BuildRecord,
        config: BuildConfiguration,
        canonical: CanonicalApi,
        canonical_sha256: str,
        manifest: MCPManifest,
        manifest_bytes: bytes,
        cancellation_check: Callable[[], Awaitable[None]] | None = None,
    ) -> ValidationReportRecord:
        async with self._database.session_scope() as session:
            existing = await self._reports.get_report(session, build.id)
        if existing is not None:
            return existing
        excluded = frozenset(item.operation_key for item in config.excluded_operations)
        findings = validate_build(
            canonical,
            manifest,
            excluded_operation_keys=excluded,
            canonical_sha256=canonical_sha256,
            runtime_version=self._runtime_version,
        )
        findings.extend(
            validate_runtime_manifest_size(
                manifest_bytes,
                maximum_bytes=config.runtime_manifest_max_bytes,
            )
        )
        actual_manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        if build.manifest_sha256 != actual_manifest_sha256:
            findings.append(
                ValidationFinding(
                    code="MANIFEST_STORAGE_HASH_MISMATCH",
                    severity=FindingSeverity.ERROR,
                    stage="artifact",
                    message="Stored manifest bytes do not match the Build manifest hash",
                    details={
                        "expected": build.manifest_sha256,
                        "actual": actual_manifest_sha256,
                    },
                )
            )
        if not _has_errors(findings):
            try:
                if cancellation_check is not None:
                    await cancellation_check()
                protocol = await self._mcp.inspect_manifest(
                    manifest,
                    runtime_version=self._runtime_version,
                )
                if cancellation_check is not None:
                    await cancellation_check()
                if protocol["tool_count"] != len(manifest.enabled_tools()):
                    raise ProtocolValidationError(
                        "MCP protocol listing did not preserve all generated tools"
                    )
            except ProtocolValidationError as exc:
                findings.append(
                    ValidationFinding(
                        code="MCP_PROTOCOL_LIST_FAILED",
                        severity=FindingSeverity.ERROR,
                        stage="protocol",
                        message=str(exc),
                    )
                )
        if not _has_errors(findings):
            if not build.validation_model:
                findings.append(
                    ValidationFinding(
                        code="VALIDATION_MODEL_MISSING",
                        severity=FindingSeverity.ERROR,
                        stage="semantic",
                        message="Build has no frozen semantic validation model",
                    )
                )
            else:
                semantic = await self._semantic_review.review(
                    build_id=build.id,
                    canonical=canonical,
                    manifest=manifest,
                    model=build.validation_model,
                    max_context_chars=config.max_context_chars,
                    cancellation_check=cancellation_check,
                )
                if cancellation_check is not None:
                    await cancellation_check()
                findings.extend(_semantic_finding(item) for item in semantic)
        source_count = len(canonical.operations)
        excluded_count = len(excluded & {operation.key for operation in canonical.operations})
        expected_count = source_count - excluded_count
        generated_count = len(manifest.enabled_tools())
        blocking = sum(item.severity is FindingSeverity.ERROR for item in findings)
        warnings = sum(item.severity is FindingSeverity.WARNING for item in findings)
        overall = ValidationStatus.FAIL if blocking else ValidationStatus.PASS
        async with self._database.session_scope() as session:
            return await self._reports.create_report(
                session,
                build_id=build.id,
                overall_status=overall,
                operation_source_count=source_count,
                operation_excluded_count=excluded_count,
                operation_expected_count=expected_count,
                operation_generated_count=generated_count,
                coverage_percent=coverage_percent(
                    expected_operations=expected_count,
                    generated_tools=generated_count,
                ),
                blocking_error_count=blocking,
                warning_count=warnings,
                findings=findings,
            )


def _has_errors(findings: list[ValidationFinding]) -> bool:
    return any(item.severity is FindingSeverity.ERROR for item in findings)


def _semantic_finding(value: SemanticReviewFinding) -> ValidationFinding:
    return ValidationFinding(
        code=value.code,
        severity=(FindingSeverity.WARNING if value.severity == "warning" else FindingSeverity.INFO),
        stage="semantic",
        operation_key=value.operation_key,
        message=value.message,
    )
