from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redaction import redact
from app.domain.audit import AuditEventRecord
from app.models.audit import AuditEvent
from app.models.auth import User


def _to_domain(model: AuditEvent) -> AuditEventRecord:
    return AuditEventRecord(
        id=model.id,
        actor_user_id=model.actor_user_id,
        event_type=model.event_type,
        entity_type=model.entity_type,
        entity_id=model.entity_id,
        project_id=model.project_id,
        request_id=model.request_id,
        metadata=model.metadata_json,
        created_at=model.created_at,
    )


class AuditRepository:
    async def append(
        self,
        session: AsyncSession,
        *,
        actor_user_id: UUID | None,
        event_type: str,
        entity_type: str,
        entity_id: UUID | None = None,
        project_id: UUID | None = None,
        request_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AuditEventRecord:
        safe_metadata = redact(metadata or {})
        model = AuditEvent(
            actor_user_id=actor_user_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            project_id=project_id,
            request_id=request_id,
            metadata_json=safe_metadata,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _to_domain(model)

    async def list(
        self,
        session: AsyncSession,
        *,
        project_id: UUID | None = None,
        event_type: str | None = None,
        actor: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEventRecord]:
        statement: Select[tuple[AuditEvent]] = select(AuditEvent)
        if project_id is not None:
            statement = statement.where(AuditEvent.project_id == project_id)
        if event_type is not None:
            statement = statement.where(AuditEvent.event_type == event_type)
        if actor:
            pattern = f"%{actor.strip()}%"
            statement = statement.join(
                User,
                User.id == AuditEvent.actor_user_id,
                isouter=True,
            ).where(or_(User.email.ilike(pattern), User.display_name.ilike(pattern)))
        if created_from is not None:
            statement = statement.where(AuditEvent.created_at >= created_from)
        if created_to is not None:
            statement = statement.where(AuditEvent.created_at < created_to)
        result = await session.scalars(
            statement.order_by(AuditEvent.created_at.desc()).limit(min(limit, 500)).offset(offset)
        )
        return [_to_domain(model) for model in result]

    async def count(
        self,
        session: AsyncSession,
        *,
        project_id: UUID | None = None,
        event_type: str | None = None,
        actor: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> int:
        statement = select(func.count(AuditEvent.id))
        if project_id is not None:
            statement = statement.where(AuditEvent.project_id == project_id)
        if event_type is not None:
            statement = statement.where(AuditEvent.event_type == event_type)
        if actor:
            pattern = f"%{actor.strip()}%"
            statement = statement.join(
                User,
                User.id == AuditEvent.actor_user_id,
                isouter=True,
            ).where(or_(User.email.ilike(pattern), User.display_name.ilike(pattern)))
        if created_from is not None:
            statement = statement.where(AuditEvent.created_at >= created_from)
        if created_to is not None:
            statement = statement.where(AuditEvent.created_at < created_to)
        return int(await session.scalar(statement) or 0)
