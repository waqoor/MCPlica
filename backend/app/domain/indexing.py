from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IndexGenerationStatus(StrEnum):
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"


class DocumentIndexGenerationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    project_id: UUID
    build_id: UUID
    embedding_model: str | None
    dimensions: int | None
    collection_name: str | None
    generation_key: str
    chunk_count: int
    chunk_manifest_storage_key: str | None
    chunk_manifest_sha256: str | None
    source_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: IndexGenerationStatus
    error_summary: str | None
    created_at: datetime
    completed_at: datetime | None
