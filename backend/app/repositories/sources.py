from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.sources import (
    BoundSourceVersionRecord,
    ProjectSourceRecord,
    SourceKind,
    SourceOrigin,
    SourceVersionRecord,
)
from app.models.source import ProjectSource, SourceVersion


def _source_to_domain(model: ProjectSource) -> ProjectSourceRecord:
    return ProjectSourceRecord(
        id=model.id,
        project_id=model.project_id,
        kind=model.kind,
        name=model.name,
        origin_type=model.origin_type,
        source_url=model.source_url,
        is_primary=model.is_primary,
        created_at=model.created_at,
    )


def _version_to_domain(model: SourceVersion) -> SourceVersionRecord:
    return SourceVersionRecord(
        id=model.id,
        source_id=model.source_id,
        content_sha256=model.content_sha256,
        media_type=model.media_type,
        storage_key=model.storage_key,
        byte_size=model.byte_size,
        detected_format=model.detected_format,
        source_etag=model.source_etag,
        source_last_modified=model.source_last_modified,
        created_by=model.created_by,
        created_at=model.created_at,
    )


class SourceRepository:
    async def list_bound_versions(
        self,
        session: AsyncSession,
        project_id: UUID,
        version_ids: list[UUID],
    ) -> list[BoundSourceVersionRecord]:
        if not version_ids:
            return []
        rows = await session.execute(
            select(ProjectSource, SourceVersion)
            .join(SourceVersion, SourceVersion.source_id == ProjectSource.id)
            .where(
                ProjectSource.project_id == project_id,
                SourceVersion.id.in_(version_ids),
            )
        )
        return [
            BoundSourceVersionRecord(
                source=_source_to_domain(source),
                version=_version_to_domain(version),
            )
            for source, version in rows.tuples()
        ]

    async def latest_bound_versions(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> list[BoundSourceVersionRecord]:
        latest = (
            select(SourceVersion.id)
            .where(SourceVersion.source_id == ProjectSource.id)
            .order_by(SourceVersion.created_at.desc(), SourceVersion.id.desc())
            .limit(1)
            .correlate(ProjectSource)
            .scalar_subquery()
        )
        rows = await session.execute(
            select(ProjectSource, SourceVersion)
            .join(SourceVersion, SourceVersion.id == latest)
            .where(ProjectSource.project_id == project_id)
            .order_by(ProjectSource.created_at.asc())
        )
        return [
            BoundSourceVersionRecord(
                source=_source_to_domain(source),
                version=_version_to_domain(version),
            )
            for source, version in rows.tuples()
        ]

    async def list_sources(
        self, session: AsyncSession, project_id: UUID
    ) -> list[ProjectSourceRecord]:
        result = await session.scalars(
            select(ProjectSource)
            .where(ProjectSource.project_id == project_id)
            .order_by(ProjectSource.created_at.asc())
        )
        return [_source_to_domain(model) for model in result]

    async def get_source(
        self, session: AsyncSession, source_id: UUID
    ) -> ProjectSourceRecord | None:
        model = await session.get(ProjectSource, source_id)
        return _source_to_domain(model) if model else None

    async def lock_source(
        self,
        session: AsyncSession,
        source_id: UUID,
    ) -> ProjectSourceRecord | None:
        model = await session.scalar(
            select(ProjectSource).where(ProjectSource.id == source_id).with_for_update()
        )
        return _source_to_domain(model) if model else None

    async def get_primary_for_kind(
        self,
        session: AsyncSession,
        project_id: UUID,
        kind: SourceKind,
    ) -> ProjectSourceRecord | None:
        model = await session.scalar(
            select(ProjectSource).where(
                ProjectSource.project_id == project_id,
                ProjectSource.kind == kind,
                ProjectSource.is_primary.is_(True),
            )
        )
        return _source_to_domain(model) if model else None

    async def get_primary_executable(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> ProjectSourceRecord | None:
        model = await session.scalar(
            select(ProjectSource).where(
                ProjectSource.project_id == project_id,
                ProjectSource.kind.in_([SourceKind.OPENAPI, SourceKind.API_INVENTORY]),
                ProjectSource.is_primary.is_(True),
            )
        )
        return _source_to_domain(model) if model else None

    async def create_source(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        kind: SourceKind,
        name: str,
        origin_type: SourceOrigin,
        source_url: str | None,
        is_primary: bool,
    ) -> ProjectSourceRecord:
        model = ProjectSource(
            project_id=project_id,
            kind=kind,
            name=name,
            origin_type=origin_type,
            source_url=source_url,
            is_primary=is_primary,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _source_to_domain(model)

    async def list_versions(
        self, session: AsyncSession, source_id: UUID
    ) -> list[SourceVersionRecord]:
        result = await session.scalars(
            select(SourceVersion)
            .where(SourceVersion.source_id == source_id)
            .order_by(SourceVersion.created_at.desc())
        )
        return [_version_to_domain(model) for model in result]

    async def latest_version(
        self, session: AsyncSession, source_id: UUID
    ) -> SourceVersionRecord | None:
        model = await session.scalar(
            select(SourceVersion)
            .where(SourceVersion.source_id == source_id)
            .order_by(SourceVersion.created_at.desc())
            .limit(1)
        )
        return _version_to_domain(model) if model else None

    async def get_version(
        self, session: AsyncSession, version_id: UUID
    ) -> SourceVersionRecord | None:
        model = await session.get(SourceVersion, version_id)
        return _version_to_domain(model) if model else None

    async def get_version_by_hash(
        self, session: AsyncSession, source_id: UUID, content_sha256: str
    ) -> SourceVersionRecord | None:
        model = await session.scalar(
            select(SourceVersion).where(
                SourceVersion.source_id == source_id,
                SourceVersion.content_sha256 == content_sha256,
            )
        )
        return _version_to_domain(model) if model else None

    async def create_version(
        self,
        session: AsyncSession,
        *,
        source_id: UUID,
        content_sha256: str,
        media_type: str,
        storage_key: str,
        byte_size: int,
        detected_format: str,
        source_etag: str | None,
        source_last_modified: str | None,
        created_by: UUID,
    ) -> SourceVersionRecord:
        model = SourceVersion(
            source_id=source_id,
            content_sha256=content_sha256,
            media_type=media_type,
            storage_key=storage_key,
            byte_size=byte_size,
            detected_format=detected_format,
            source_etag=source_etag,
            source_last_modified=source_last_modified,
            created_by=created_by,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _version_to_domain(model)
