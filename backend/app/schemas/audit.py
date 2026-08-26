from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    actor_user_id: UUID | None
    event_type: str
    entity_type: str
    entity_id: UUID | None
    project_id: UUID | None
    request_id: str | None
    metadata: dict[str, object]
    created_at: datetime


class AuditPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuditEventRead]
    total: int
    page: int
    page_size: int
