from datetime import datetime
from typing import Literal
from uuid import UUID

from mcp_contracts.json_types import JsonObject
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.build_admission import BuildAdmissionState
from app.domain.builds import BuildStatus, BuildTrigger
from app.domain.validation import FindingSeverity, ValidationStatus


class BuildCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger: Literal[BuildTrigger.INITIAL] = BuildTrigger.INITIAL


class BuildRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    project_id: UUID
    sequence: int
    status: BuildStatus
    pipeline_stage: BuildStatus | None
    trigger: BuildTrigger
    executable_configuration_sha256: str | None
    canonical_snapshot_id: UUID | None
    previous_build_id: UUID | None
    compiler_version: str
    manifest_schema_version: str
    runtime_compatibility: str
    analysis_model: str | None
    validation_model: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    prompt_bundle_version: str | None
    manifest_sha256: str | None
    artifact_sha256: str | None
    error_code: str | None
    error_summary: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    cancellation_requested_at: datetime | None
    cancellation_requested_by: UUID | None
    cancellation_acknowledged_at: datetime | None
    admission_acquired_at: datetime | None
    admission_enqueued_at: datetime | None
    admission_heartbeat_at: datetime | None
    admission_lease_expires_at: datetime | None
    admission_released_at: datetime | None
    admission_attempt_count: int


class BuildPageRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[BuildRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    has_active: bool


class BuildMetricsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    active: int = Field(ge=0)
    failed: int = Field(ge=0)


class QueuedBuildAdmissionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_id: UUID
    project_id: UUID
    status: BuildStatus
    state: BuildAdmissionState
    position: int | None
    admitted_at: datetime | None
    lease_expires_at: datetime | None


class BuildAdmissionOverviewRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configured_concurrency: int
    effective_concurrency: int
    waiting_count: int
    entries: list[QueuedBuildAdmissionRead]


class ValidationSourceRefRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_version_id: UUID
    path: str


class ValidationFindingRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: FindingSeverity
    stage: str
    operation_key: str | None
    source_ref: ValidationSourceRefRead | None
    message: str
    details: JsonObject = Field(default_factory=dict)


class ValidationReportRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    build_id: UUID
    overall_status: ValidationStatus
    operation_source_count: int
    operation_excluded_count: int
    operation_expected_count: int
    operation_generated_count: int
    coverage_percent: float
    blocking_error_count: int
    warning_count: int
    findings: list[ValidationFindingRead]
    created_at: datetime


class OperationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    source_operation_id: str | None
    method: str
    path_template: str
    tool_name: str | None
    title: str | None
    source_summary: str | None
    source_description: str | None
    enriched_description: str | None
    input_schema: JsonObject | None
    auth_mapping: list[str]
    provenance: list[JsonObject]
    semantic_warnings: list[str]
    confidence: float | None
    excluded_in_build: bool
    build_exclusion_id: UUID | None
    build_exclusion_reason: str | None


class OperationPageItemRead(OperationRead):
    current_exclusion_id: UUID | None
    current_exclusion_reason: str | None


class OperationPageRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OperationPageItemRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    policy_change_count: int = Field(ge=0)


class OperationChangeRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    changes: list[str]


class BuildDiffRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    added_operations: list[str]
    removed_operations: list[str]
    changed_operations: list[OperationChangeRead]
    unchanged_operations: list[str]
    changed_schemas: list[str]
    changed_security: list[str]
    changed_documents: list[UUID]


class OperationExclusionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=5, max_length=2_000)

    @field_validator("operation_key", "reason", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("value must be a string")
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be blank")
        return normalized


class OperationExclusionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    build_id: UUID | None
    operation_key: str
    reason_code: str
    reason: str
    is_user_requested: bool
    created_by: UUID
    created_at: datetime


class BuildAIRunRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    build_id: UUID
    run_key: str
    stage: str
    operation_key: str | None
    provider: str
    model: str
    prompt_template_id: str
    prompt_template_version: str
    input_context_sha256: str
    retrieved_chunk_ids: list[str]
    response_schema_id: str
    response_sha256: str | None
    usage: dict[str, object] | None
    cost: dict[str, object] | None
    latency_ms: int | None
    status: str
    error_code: str | None
    created_at: datetime
