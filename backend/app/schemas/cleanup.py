from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.cleanup import CleanupJobKind, CleanupJobStatus


class CleanupJobRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    kind: CleanupJobKind
    status: CleanupJobStatus
    project_id: UUID | None
    requested_by: UUID | None
    request_id: str | None
    total_targets: int
    completed_targets: int
    skipped_targets: int
    failed_targets: int
    last_error_code: str | None
    last_error_summary: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
