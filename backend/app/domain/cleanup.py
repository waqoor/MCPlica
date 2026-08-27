from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CleanupJobKind(StrEnum):
    PROJECT_DELETE = "project_delete"
    SOURCE_DELETE = "source_delete"
    RETENTION = "retention"
    ORPHAN_GUARD = "orphan_guard"


class CleanupJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"


class CleanupTargetType(StrEnum):
    OBJECT = "object"
    VECTOR_GENERATION = "vector_generation"


class CleanupTargetStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    SKIPPED_REFERENCED = "skipped_referenced"
    FAILED = "failed"


class CleanupTargetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    job_id: UUID
    target_type: CleanupTargetType
    status: CleanupTargetStatus
    storage_key: str | None
    collection_name: str | None
    vector_project_id: UUID | None
    generation_id: UUID | None
    attempt_count: int = Field(ge=0)
    next_attempt_at: datetime
    lease_expires_at: datetime | None
    last_error_code: str | None
    last_error_summary: str | None


class CleanupJobRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    kind: CleanupJobKind
    status: CleanupJobStatus
    project_id: UUID | None
    requested_by: UUID | None
    request_id: str | None
    total_targets: int = Field(ge=0)
    completed_targets: int = Field(ge=0)
    skipped_targets: int = Field(ge=0)
    failed_targets: int = Field(ge=0)
    last_error_code: str | None
    last_error_summary: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
