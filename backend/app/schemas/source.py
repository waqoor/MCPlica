from datetime import datetime
from typing import Literal
from uuid import UUID

from mcp_contracts.json_types import JsonObject
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.indexing import IndexGenerationStatus
from app.domain.sources import SourceKind, SourceOrigin


class SourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: SourceKind
    name: str = Field(min_length=1, max_length=200)
    origin_type: SourceOrigin
    source_url: AnyHttpUrl | None = None
    is_primary: bool = False

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @model_validator(mode="after")
    def validate_origin(self) -> "SourceCreate":
        if self.origin_type is SourceOrigin.URL and self.source_url is None:
            raise ValueError("URL sources require source_url")
        if self.origin_type is SourceOrigin.UPLOAD and self.source_url is not None:
            raise ValueError("uploaded sources cannot define source_url")
        return self


class SourceRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    project_id: UUID
    kind: SourceKind
    name: str
    origin_type: SourceOrigin
    source_url: str | None
    is_primary: bool
    created_at: datetime
    current_version_id: UUID | None
    current_version_selected_at: datetime | None
    last_observed_at: datetime | None
    last_observed_etag: str | None
    last_observed_last_modified: str | None


class SourceUrlCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    kind: SourceKind
    name: str = Field(min_length=1, max_length=200)
    source_url: AnyHttpUrl
    is_primary: bool = False

    @field_validator("name")
    @classmethod
    def normalize_url_source_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class SourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_primary: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_updated_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @model_validator(mode="after")
    def require_change(self) -> "SourceUpdate":
        if self.name is None and self.is_primary is None:
            raise ValueError("at least one source field must be provided")
        return self


class SourceVersionRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    source_id: UUID
    content_sha256: str
    media_type: str
    byte_size: int
    detected_format: str
    source_etag: str | None
    source_last_modified: str | None
    created_by: UUID
    created_at: datetime
    deduplicated: bool = False


class SourceVersionSummaryRead(SourceVersionRead):
    operation_count: int | None = Field(default=None, ge=0)
    indexed_chunk_count: int | None = Field(default=None, ge=0)
    metadata_build_id: UUID | None = None
    index_generation_id: UUID | None = None


class SourceSummaryRead(SourceRead):
    latest_version: SourceVersionSummaryRead | None
    version_count: int = Field(ge=0)
    health: Literal["missing", "pending", "valid", "invalid"]


class SourcePageRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SourceSummaryRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class SourceVersionPageRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SourceVersionRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class SourceCreationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: SourceRead
    version: SourceVersionRead


class SourceIssueRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_version_id: UUID
    stage: str
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    pointer: str | None = None
    line: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=1)
    details: JsonObject


class SourceVersionMetadataRead(SourceVersionRead):
    parse_status: Literal["pending", "valid", "invalid"]
    spec_version: str | None
    operation_count: int | None
    servers: list[str]
    auth_schemes: list[str]
    errors: list[SourceIssueRead]
    preview_markdown: str | None
    indexed_chunk_count: int | None
    embedding_model: str | None
    embedding_dimensions: int | None
    index_status: IndexGenerationStatus | None
    metadata_build_id: UUID | None
    index_generation_id: UUID | None


class ServerCandidateRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    ref: str
    url: str
    description: str | None
    scope: Literal["root", "path", "operation", "project_default", "inventory"]
    source_pointer: str
    applicable_operation_keys: list[str]


class OperationServerRoutingRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    operation_key: str
    method: str
    path: str
    candidate_refs: list[str]
    selected_server_ref: str | None
    configured_server_ref: str | None
    selection_required: bool
    selection_error: str | None


class SecuritySchemeDiscoveryRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    name: str
    type: str
    location: str | None
    parameter_name: str | None
    token_url: str | None
    advertised_scopes: list[str]
    applicable_operation_keys: list[str]
    optional_for_all_operations: bool
    source_pointer: str


class OperationSecurityRequirementRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    operation_key: str
    alternatives: list[dict[str, list[str]]]
    anonymous_allowed: bool


class SourceConfigurationDiscoveryRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    source_version_ids: list[UUID]
    configuration_sha256: str
    servers: list[ServerCandidateRead]
    operations: list[OperationServerRoutingRead]
    security_schemes: list[SecuritySchemeDiscoveryRead]
    security_requirements: list[OperationSecurityRequirementRead]
    routing_complete: bool
