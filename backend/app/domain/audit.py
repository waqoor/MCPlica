from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEventRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    actor_user_id: UUID | None
    event_type: str
    entity_type: str
    entity_id: UUID | None
    project_id: UUID | None
    request_id: str | None
    metadata: dict[str, object]
    created_at: datetime
