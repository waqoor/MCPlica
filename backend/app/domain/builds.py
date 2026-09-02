from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from mcp_contracts.json_types import JsonObject
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.credentials import CredentialScheme


class BuildStatus(StrEnum):
    QUEUED = "QUEUED"
    INGESTING = "INGESTING"
    PARSING = "PARSING"
    INDEXING = "INDEXING"
    ANALYZING = "ANALYZING"
    COMPILING = "COMPILING"
    VALIDATING = "VALIDATING"
    PACKAGING = "PACKAGING"
    READY = "READY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class BuildTrigger(StrEnum):
    INITIAL = "initial"
    SOURCE_CHANGE = "source_change"
    MANUAL_REVIEW = "manual_review"
    MANUAL_REBUILD = "manual_rebuild"


class BuildExclusionSnapshot(BaseModel):
    """An exclusion frozen at build creation; later rule edits cannot mutate a Build."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    operation_key: str = Field(min_length=1, max_length=160)
    reason_code: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=2_000)


class BuildCredentialSnapshot(BaseModel):
    """Non-secret credential metadata used for deterministic auth-profile selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    scheme_type: CredentialScheme
    metadata: JsonObject = Field(default_factory=dict)


class BuildSecuritySelection(BaseModel):
    """The exact executable auth alternative frozen for one operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scheme_name: str
    credential_ref: str
    scopes: list[str] = Field(default_factory=list)
    token_auth_method: Literal["client_secret_basic", "client_secret_post"] = "client_secret_basic"


class BuildConfiguration(BaseModel):
    """All mutable installation/project inputs that affect reproducible compilation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    executable_configuration_sha256: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
    )
    excluded_operations: list[BuildExclusionSnapshot] = Field(
        default_factory=lambda: list[BuildExclusionSnapshot]()
    )
    credentials: list[BuildCredentialSnapshot] = Field(
        default_factory=lambda: list[BuildCredentialSnapshot]()
    )
    # Legacy build rows may contain the former build-bound access mode. It is
    # deliberately ignored for new builds and at deployment time.
    inbound_auth_mode: Literal["static_bearer", "oidc", "none"] | None = None
    default_base_url: str | None = None
    active_server_ref: str | None = None
    server_mappings: dict[str, str] = Field(default_factory=dict)
    include_documentation_in_analysis: bool
    max_operations: int = Field(ge=1)
    max_context_chars: int = Field(ge=1_000)
    max_ai_concurrency: int = Field(ge=1, le=32)
    retrieval_top_k: int = Field(ge=1, le=50)
    source_max_bytes: int = Field(ge=1)
    document_max_bytes: int = Field(ge=1)
    document_max_text_chars: int = Field(ge=1_000)
    pdf_max_pages: int = Field(ge=1)
    documentation_chunk_chars: int = Field(ge=500)
    documentation_chunk_overlap_chars: int = Field(ge=0)
    max_document_chunks: int = Field(ge=1)
    max_document_parse_concurrency: int = Field(default=4, ge=1, le=32)
    embedding_batch_size: int = Field(ge=1)
    max_embedding_concurrency: int = Field(ge=1, le=32)
    runtime_timeout_ms: int = Field(ge=100, le=300_000)
    runtime_max_request_bytes: int = Field(ge=1_024, le=100_000_000)
    runtime_max_response_bytes: int = Field(ge=1_024, le=50_000_000)
    runtime_manifest_max_bytes: int = Field(ge=1_024, le=50_000_000)
    artifact_max_bytes: int = Field(ge=1_024)

    @model_validator(mode="after")
    def validate_chunking(self) -> "BuildConfiguration":
        if self.documentation_chunk_overlap_chars >= self.documentation_chunk_chars:
            raise ValueError("documentation chunk overlap must be smaller than chunk size")
        return self


PIPELINE_STATUSES = (
    BuildStatus.QUEUED,
    BuildStatus.INGESTING,
    BuildStatus.PARSING,
    BuildStatus.INDEXING,
    BuildStatus.ANALYZING,
    BuildStatus.COMPILING,
    BuildStatus.VALIDATING,
    BuildStatus.PACKAGING,
    BuildStatus.READY,
)
TERMINAL_STATUSES = frozenset({BuildStatus.READY, BuildStatus.FAILED, BuildStatus.CANCELLED})


def next_status(current: BuildStatus) -> BuildStatus:
    if current in TERMINAL_STATUSES:
        raise ValueError(f"Build status {current.value} is terminal")
    return PIPELINE_STATUSES[PIPELINE_STATUSES.index(current) + 1]


class BuildRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    project_id: UUID
    sequence: int = Field(ge=1)
    status: BuildStatus
    pipeline_stage: BuildStatus | None = None
    trigger: BuildTrigger
    executable_configuration_sha256: str | None = None
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
    enrichment_sha256: str | None
    manifest_sha256: str | None
    artifact_sha256: str | None
    manifest_storage_key: str | None
    artifact_storage_key: str | None
    error_code: str | None
    error_summary: str | None
    requested_by: UUID
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    cancellation_requested_at: datetime | None = None
    cancellation_requested_by: UUID | None = None
    cancellation_acknowledged_at: datetime | None = None
    admission_token: UUID | None = None
    admission_acquired_at: datetime | None = None
    admission_enqueued_at: datetime | None = None
    admission_heartbeat_at: datetime | None = None
    admission_lease_expires_at: datetime | None = None
    admission_released_at: datetime | None = None
    admission_attempt_count: int = Field(default=0, ge=0)


class BuildAIRunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

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
    response: JsonObject | None
    usage: JsonObject | None
    cost: JsonObject | None
    latency_ms: int | None
    status: str
    error_code: str | None
    created_at: datetime


class OperationChange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_key: str
    changes: list[str]


class BuildDiff(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    added_operations: list[str] = Field(default_factory=list)
    removed_operations: list[str] = Field(default_factory=list)
    changed_operations: list[OperationChange] = Field(
        default_factory=lambda: list[OperationChange]()
    )
    unchanged_operations: list[str] = Field(default_factory=list)
    changed_schemas: list[str] = Field(default_factory=list)
    changed_security: list[str] = Field(default_factory=list)
    changed_documents: list[UUID] = Field(default_factory=lambda: list[UUID]())


class BuildOperationView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

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
    auth_mapping: list[str] = Field(default_factory=lambda: list[str]())
    provenance: list[JsonObject] = Field(default_factory=lambda: list[JsonObject]())
    semantic_warnings: list[str] = Field(default_factory=lambda: list[str]())
    confidence: float | None
    excluded_in_build: bool
    build_exclusion_id: UUID | None
    build_exclusion_reason: str | None


class BuildOperationPageItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: BuildOperationView
    current_exclusion_id: UUID | None
    current_exclusion_reason: str | None
