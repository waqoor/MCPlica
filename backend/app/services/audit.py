from datetime import datetime
from uuid import UUID

from app.clients.database import DatabaseClient
from app.core.exceptions import ValidationError
from app.domain.audit import AuditEventRecord
from app.repositories.audit import AuditRepository


class AuditService:
    def __init__(self, database: DatabaseClient, repository: AuditRepository) -> None:
        self._database = database
        self._repository = repository

    async def list(
        self,
        *,
        project_id: UUID | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
        actor: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> tuple[list[AuditEventRecord], int]:
        for label, value in (("from", created_from), ("to", created_to)):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValidationError(f"Audit {label} timestamp must include a UTC offset")
        if created_from is not None and created_to is not None and created_from > created_to:
            raise ValidationError("Audit from timestamp must not be later than to timestamp")
        async with self._database.session_scope() as session:
            items = await self._repository.list(
                session,
                project_id=project_id,
                event_type=event_type,
                actor=actor,
                created_from=created_from,
                created_to=created_to,
                limit=limit,
                offset=offset,
            )
            total = await self._repository.count(
                session,
                project_id=project_id,
                event_type=event_type,
                actor=actor,
                created_from=created_from,
                created_to=created_to,
            )
            return items, total
