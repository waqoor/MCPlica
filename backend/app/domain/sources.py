import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from mcp_contracts.json_types import JsonObject
from pydantic import BaseModel, ConfigDict, Field

from app.domain.indexing import IndexGenerationStatus


class SourceKind(StrEnum):
    OPENAPI = "openapi"
    API_INVENTORY = "api_inventory"
    DOCUMENTATION = "documentation"


class SourceOrigin(StrEnum):
    UPLOAD = "upload"
    URL = "url"


class ProjectSourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    project_id: UUID
    kind: SourceKind
    name: str
    origin_type: SourceOrigin
    source_url: str | None
    is_primary: bool
    created_at: datetime


class SourceVersionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    source_id: UUID
    content_sha256: str
    media_type: str
    storage_key: str
    byte_size: int
    detected_format: str
    source_etag: str | None
    source_last_modified: str | None
    created_by: UUID
    created_at: datetime


class BoundSourceVersionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: ProjectSourceRecord
    version: SourceVersionRecord


class SourceSummaryRecord(BaseModel):
    """One bounded source-list row without per-source API fan-out."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: ProjectSourceRecord
    latest_version: SourceVersionRecord | None = None
    version_count: int = Field(ge=0)
    health: Literal["missing", "pending", "valid", "invalid"]
    metadata_build_id: UUID | None = None
    operation_count: int | None = Field(default=None, ge=0)
    indexed_chunk_count: int | None = Field(default=None, ge=0)
    index_generation_id: UUID | None = None


SourceFindingSeverity = Literal["error", "warning", "info"]


class SourceFindingRecord(BaseModel):
    """A durable finding attributed to one immutable source version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    build_id: UUID
    source_version_id: UUID
    stage: str
    code: str
    severity: SourceFindingSeverity
    message: str
    pointer: str | None = None
    line: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=1)
    details: JsonObject = Field(default_factory=dict)
    created_at: datetime


class SourceIssueRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_version_id: UUID
    stage: str
    code: str
    severity: SourceFindingSeverity
    message: str
    pointer: str | None = None
    line: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=1)
    details: JsonObject = Field(default_factory=dict)


class SourceVersionMetadataRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: SourceVersionRecord
    parse_status: Literal["pending", "valid", "invalid"]
    spec_version: str | None = None
    operation_count: int | None = None
    servers: list[str] = Field(default_factory=lambda: list[str]())
    auth_schemes: list[str] = Field(default_factory=lambda: list[str]())
    errors: list[SourceIssueRecord] = Field(default_factory=lambda: list[SourceIssueRecord]())
    preview_markdown: str | None = None
    indexed_chunk_count: int | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    index_status: IndexGenerationStatus | None = None
    metadata_build_id: UUID | None = None
    index_generation_id: UUID | None = None


class ServerCandidateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: str
    url: str
    description: str | None = None
    scope: Literal["root", "path", "operation", "project_default", "inventory"]
    source_pointer: str
    applicable_operation_keys: list[str] = Field(default_factory=list)


class OperationServerRoutingRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_key: str
    method: str
    path: str
    candidate_refs: list[str] = Field(min_length=1)
    selected_server_ref: str | None = None
    configured_server_ref: str | None = None
    selection_required: bool
    selection_error: str | None = None


class SecuritySchemeDiscoveryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    type: str
    location: str | None = None
    parameter_name: str | None = None
    token_url: str | None = None
    advertised_scopes: list[str] = Field(default_factory=list)
    applicable_operation_keys: list[str] = Field(default_factory=list)
    optional_for_all_operations: bool = False
    source_pointer: str


class OperationSecurityRequirementRecord(BaseModel):
    """Exact source-declared security alternatives for one operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_key: str
    alternatives: list[dict[str, list[str]]] = Field(
        default_factory=lambda: list[dict[str, list[str]]]()
    )
    anonymous_allowed: bool = False


class SourceConfigurationDiscoveryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_version_ids: list[UUID] = Field(min_length=1)
    configuration_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    servers: list[ServerCandidateRecord]
    operations: list[OperationServerRoutingRecord]
    security_schemes: list[SecuritySchemeDiscoveryRecord]
    security_requirements: list[OperationSecurityRequirementRecord]
    routing_complete: bool


def source_configuration_fingerprint(
    *,
    source_version_ids: list[UUID],
    default_base_url: str | None,
    active_server_ref: str | None,
    server_mappings: dict[str, str],
) -> str:
    value = json.dumps(
        {
            "source_version_ids": sorted(str(value) for value in source_version_ids),
            "default_base_url": default_base_url,
            "active_server_ref": active_server_ref,
            "server_mappings": dict(sorted(server_mappings.items())),
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(value).hexdigest()
