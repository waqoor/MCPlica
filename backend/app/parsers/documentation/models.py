from uuid import UUID

from mcp_contracts.json_types import JsonValue
from pydantic import BaseModel, ConfigDict, Field


class DocumentSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: list[str] = Field(min_length=1)
    heading: str | None = None
    text: str
    ordinal: int = Field(ge=0)


class NormalizedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_version_id: UUID
    title: str | None = None
    text: str
    sections: list[DocumentSection] = Field(min_length=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str = Field(pattern=r"^chunk_[a-f0-9]{64}$")
    project_id: UUID
    generation_id: UUID
    source_version_id: UUID
    source_kind: str = "documentation"
    title: str | None = None
    section_path: list[str] = Field(min_length=1)
    operation_keys: list[str] = Field(default_factory=list)
    text: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
