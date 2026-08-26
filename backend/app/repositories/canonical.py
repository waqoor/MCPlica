from uuid import UUID

from mcp_contracts import CanonicalApi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.canonicalization import CanonicalSnapshotRecord
from app.models.canonical import CanonicalSnapshot


def _to_domain(model: CanonicalSnapshot) -> CanonicalSnapshotRecord:
    return CanonicalSnapshotRecord(
        id=model.id,
        project_id=model.project_id,
        schema_version=model.schema_version,
        canonical_sha256=model.canonical_sha256,
        canonical=CanonicalApi.model_validate(model.canonical_json),
        source_version_ids=model.source_version_ids,
        created_at=model.created_at,
    )


class CanonicalRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        canonical: CanonicalApi,
        canonical_sha256: str,
        source_version_ids: list[UUID],
    ) -> CanonicalSnapshotRecord:
        model = CanonicalSnapshot(
            project_id=project_id,
            schema_version=canonical.schema_version,
            canonical_sha256=canonical_sha256,
            canonical_json=canonical.model_dump(mode="json", by_alias=True),
            source_version_ids=source_version_ids,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _to_domain(model)

    async def get(
        self,
        session: AsyncSession,
        snapshot_id: UUID,
    ) -> CanonicalSnapshotRecord | None:
        model = await session.get(CanonicalSnapshot, snapshot_id)
        return _to_domain(model) if model else None

    async def latest_for_project(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> CanonicalSnapshotRecord | None:
        model = await session.scalar(
            select(CanonicalSnapshot)
            .where(CanonicalSnapshot.project_id == project_id)
            .order_by(CanonicalSnapshot.created_at.desc())
            .limit(1)
        )
        return _to_domain(model) if model else None
