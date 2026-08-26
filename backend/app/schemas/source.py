from datetime import datetime
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

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
