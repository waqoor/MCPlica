from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

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


class SourceIssueRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    severity: Literal["error", "warning"]
    message: str
    location: str | None = None


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
