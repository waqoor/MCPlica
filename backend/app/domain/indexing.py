import math
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    execution_token: UUID | None = None
    created_at: datetime
    completed_at: datetime | None


class CachedEmbeddingRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    project_id: UUID
    model_identity: str = Field(min_length=1, max_length=300)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    resolved_model: str = Field(min_length=1, max_length=300)
    dimensions: int = Field(gt=0)
    vector: list[float] = Field(min_length=1)
    created_at: datetime
    last_used_at: datetime

    @model_validator(mode="after")
    def validate_vector(self) -> "CachedEmbeddingRecord":
        if len(self.vector) != self.dimensions or not all(
            math.isfinite(value) for value in self.vector
        ):
            raise ValueError("Cached embedding vector metadata is invalid")
        return self
