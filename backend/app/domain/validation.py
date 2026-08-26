from datetime import datetime
from enum import StrEnum
from uuid import UUID

from mcp_contracts import SourceRef
from mcp_contracts.json_types import JsonObject
from pydantic import BaseModel, ConfigDict, Field


class FindingSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class ValidationFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    severity: FindingSeverity
    stage: str
    operation_key: str | None = None
    source_ref: SourceRef | None = None
    message: str
    details: JsonObject = Field(default_factory=dict)


class ValidationReportRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

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
    findings: list[ValidationFinding]
    created_at: datetime


class OperationExclusionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    project_id: UUID
    build_id: UUID | None
    operation_key: str
    reason_code: str
    reason: str
    is_user_requested: bool
    created_by: UUID
    created_at: datetime
