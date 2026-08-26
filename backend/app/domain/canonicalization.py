from datetime import datetime
from uuid import UUID

from mcp_contracts import CanonicalApi
from pydantic import BaseModel, ConfigDict, Field


class CanonicalSnapshotRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    project_id: UUID
    schema_version: str
    canonical_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    canonical: CanonicalApi
    source_version_ids: list[UUID]
    created_at: datetime
