from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
