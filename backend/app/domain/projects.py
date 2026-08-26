from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProjectRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    name: str
    slug: str
    description: str | None
    default_base_url: str | None
    active_server_ref: str | None
    mcp_hostname: str
    is_enabled: bool
    active_build_id: UUID | None
    active_deployment_id: UUID | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
