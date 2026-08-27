import hashlib
from typing import cast
from uuid import UUID

from mcp_contracts.json_types import JsonObject
from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.builds import BuildStatus
from app.domain.sources import (
    BoundSourceVersionRecord,
    ProjectSourceRecord,
    SourceFindingRecord,
    SourceFindingSeverity,
    SourceKind,
    SourceOrigin,
    SourceSummaryRecord,
    SourceVersionRecord,
)
from app.models.build import Build, BuildSourceVersion
from app.models.source import ProjectSource, SourceFinding, SourceVersion


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


def _finding_to_domain(model: SourceFinding) -> SourceFindingRecord:
    return SourceFindingRecord(
        id=model.id,
        build_id=model.build_id,
        source_version_id=model.source_version_id,
        stage=model.stage,
        code=model.code,
        severity=cast(SourceFindingSeverity, model.severity),
        message=model.message,
        pointer=model.pointer,
        line=model.line,
        column=model.column,
        details=cast(JsonObject, model.details_json),
        created_at=model.created_at,
    )


def _finding_key(
    *,
    stage: str,
    code: str,
    pointer: str | None,
    line: int | None,
    column: int | None,
) -> str:
    identity = "\x00".join((stage, code, pointer or "", str(line or ""), str(column or "")))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


class SourceRepository:
    async def upsert_finding(
        self,
        session: AsyncSession,
        *,
        build_id: UUID,
        source_version_id: UUID,
        stage: str,
        code: str,
        severity: SourceFindingSeverity,
        message: str,
        pointer: str | None,
        line: int | None,
        column: int | None,
        details: JsonObject,
    ) -> SourceFindingRecord:
        finding_key = _finding_key(
            stage=stage,
            code=code,
            pointer=pointer,
            line=line,
            column=column,
        )
        statement = (
            insert(SourceFinding)
            .values(
                build_id=build_id,
                source_version_id=source_version_id,
                finding_key=finding_key,
                stage=stage,
                code=code,
                severity=severity,
                message=message,
                pointer=pointer,
                line=line,
                column=column,
                details_json=details,
            )
            .on_conflict_do_update(
                constraint="uq_source_findings_build_source_key",
                set_={
                    "severity": severity,
                    "message": message,
                    "pointer": pointer,
                    "line_number": line,
                    "column_number": column,
                    "details": details,
                },
            )
            .returning(SourceFinding)
        )
        model = (await session.scalars(statement)).one()
        return _finding_to_domain(model)

    async def list_findings_for_version(
        self,
        session: AsyncSession,
        source_version_id: UUID,
        *,
        build_id: UUID | None = None,
    ) -> list[SourceFindingRecord]:
        statement = select(SourceFinding).where(
            SourceFinding.source_version_id == source_version_id
        )
        if build_id is not None:
            statement = statement.where(SourceFinding.build_id == build_id)
        result = await session.scalars(
            statement.order_by(SourceFinding.created_at.asc(), SourceFinding.id.asc())
        )
        return [_finding_to_domain(model) for model in result]

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

    async def list_source_summaries(
        self,
        session: AsyncSession,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SourceSummaryRecord], int]:
        total = int(
            await session.scalar(
                select(func.count(ProjectSource.id)).where(ProjectSource.project_id == project_id)
            )
            or 0
        )
        source_models = list(
            await session.scalars(
                select(ProjectSource)
                .where(ProjectSource.project_id == project_id)
                .order_by(ProjectSource.created_at.asc(), ProjectSource.id.asc())
                .limit(limit)
                .offset(offset)
            )
        )
        if not source_models:
            return [], total

        source_ids = [model.id for model in source_models]
        counts = {
            source_id: int(count)
            for source_id, count in (
                await session.execute(
                    select(SourceVersion.source_id, func.count(SourceVersion.id))
                    .where(SourceVersion.source_id.in_(source_ids))
                    .group_by(SourceVersion.source_id)
                )
            ).tuples()
        }
        ranked_versions = (
            select(
                SourceVersion.id.label("version_id"),
                SourceVersion.source_id.label("source_id"),
                func.row_number()
                .over(
                    partition_by=SourceVersion.source_id,
                    order_by=(SourceVersion.created_at.desc(), SourceVersion.id.desc()),
                )
                .label("position"),
            )
            .where(SourceVersion.source_id.in_(source_ids))
            .subquery()
        )
        latest_ids = {
            source_id: version_id
            for version_id, source_id in (
                await session.execute(
                    select(ranked_versions.c.version_id, ranked_versions.c.source_id).where(
                        ranked_versions.c.position == 1
                    )
                )
            ).tuples()
        }
        version_models = {
            model.id: model
            for model in await session.scalars(
                select(SourceVersion).where(SourceVersion.id.in_(latest_ids.values()))
            )
        }

        latest_builds: dict[UUID, tuple[UUID, BuildStatus]] = {}
        if latest_ids:
            build_rows = (
                await session.execute(
                    select(BuildSourceVersion.source_version_id, Build.id, Build.status)
                    .join(Build, Build.id == BuildSourceVersion.build_id)
                    .where(BuildSourceVersion.source_version_id.in_(latest_ids.values()))
                    .order_by(
                        BuildSourceVersion.source_version_id,
                        Build.created_at.desc(),
                        Build.id.desc(),
                    )
                )
            ).tuples()
            for version_id, build_id, status in build_rows:
                latest_builds.setdefault(version_id, (build_id, status))
        latest_build_ids = [value[0] for value in latest_builds.values()]
        error_pairs: set[tuple[UUID, UUID]] = set()
        if latest_build_ids:
            error_pairs = {
                (version_id, build_id)
                for version_id, build_id in (
                    await session.execute(
                        select(SourceFinding.source_version_id, SourceFinding.build_id).where(
                            SourceFinding.source_version_id.in_(latest_ids.values()),
                            SourceFinding.build_id.in_(latest_build_ids),
                            SourceFinding.severity == "error",
                        )
                    )
                ).tuples()
            }

        summaries: list[SourceSummaryRecord] = []
        for source_model in source_models:
            version_id = latest_ids.get(source_model.id)
            version_model = version_models.get(version_id) if version_id is not None else None
            if version_model is None:
                health = "missing"
            else:
                latest_build = latest_builds.get(version_model.id)
                if latest_build is not None and (version_model.id, latest_build[0]) in error_pairs:
                    health = "invalid"
                elif latest_build is not None and latest_build[1] is BuildStatus.READY:
                    health = "valid"
                else:
                    health = "pending"
            summaries.append(
                SourceSummaryRecord(
                    source=_source_to_domain(source_model),
                    latest_version=(
                        _version_to_domain(version_model) if version_model is not None else None
                    ),
                    version_count=counts.get(source_model.id, 0),
                    health=health,
                    metadata_build_id=(
                        latest_builds[version_model.id][0]
                        if version_model is not None and version_model.id in latest_builds
                        else None
                    ),
                )
            )
        return summaries, total

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

    async def get_versioned_primary_executable(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> ProjectSourceRecord | None:
        model = await session.scalar(
            select(ProjectSource).where(
                ProjectSource.project_id == project_id,
                ProjectSource.kind.in_([SourceKind.OPENAPI, SourceKind.API_INVENTORY]),
                ProjectSource.is_primary.is_(True),
                exists(select(SourceVersion.id).where(SourceVersion.source_id == ProjectSource.id)),
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
        source_id: UUID | None = None,
    ) -> ProjectSourceRecord:
        model = ProjectSource(
            project_id=project_id,
            kind=kind,
            name=name,
            origin_type=origin_type,
            source_url=source_url,
            is_primary=is_primary,
        )
        if source_id is not None:
            model.id = source_id
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _source_to_domain(model)

    async def update_name(
        self,
        session: AsyncSession,
        source_id: UUID,
        name: str,
    ) -> ProjectSourceRecord | None:
        updated_id = await session.scalar(
            update(ProjectSource)
            .where(ProjectSource.id == source_id)
            .values(name=name)
            .returning(ProjectSource.id)
        )
        if updated_id is None:
            return None
        return await self.get_source(session, source_id)

    async def promote_executable(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        source_id: UUID,
    ) -> ProjectSourceRecord | None:
        target = await self.lock_source(session, source_id)
        if (
            target is None
            or target.project_id != project_id
            or target.kind not in {SourceKind.OPENAPI, SourceKind.API_INVENTORY}
            or await self.latest_version(session, source_id) is None
        ):
            return None
        await session.execute(
            update(ProjectSource)
            .where(
                ProjectSource.project_id == project_id,
                ProjectSource.kind.in_([SourceKind.OPENAPI, SourceKind.API_INVENTORY]),
                ProjectSource.id != source_id,
                ProjectSource.is_primary.is_(True),
            )
            .values(is_primary=False)
        )
        await session.flush()
        await session.execute(
            update(ProjectSource).where(ProjectSource.id == source_id).values(is_primary=True)
        )
        await session.flush()
        return await self.get_source(session, source_id)

    async def has_build_references(self, session: AsyncSession, source_id: UUID) -> bool:
        reference = await session.scalar(
            select(BuildSourceVersion.build_id)
            .join(SourceVersion, SourceVersion.id == BuildSourceVersion.source_version_id)
            .where(SourceVersion.source_id == source_id)
            .limit(1)
        )
        return reference is not None

    async def delete_source(self, session: AsyncSession, source_id: UUID) -> bool:
        deleted_id = await session.scalar(
            delete(ProjectSource).where(ProjectSource.id == source_id).returning(ProjectSource.id)
        )
        return deleted_id is not None

    async def first_versioned_executable(
        self,
        session: AsyncSession,
        project_id: UUID,
        *,
        exclude_source_id: UUID | None = None,
    ) -> ProjectSourceRecord | None:
        statement = (
            select(ProjectSource)
            .where(
                ProjectSource.project_id == project_id,
                ProjectSource.kind.in_([SourceKind.OPENAPI, SourceKind.API_INVENTORY]),
                exists(select(SourceVersion.id).where(SourceVersion.source_id == ProjectSource.id)),
            )
            .order_by(ProjectSource.created_at.asc(), ProjectSource.id.asc())
        )
        if exclude_source_id is not None:
            statement = statement.where(ProjectSource.id != exclude_source_id)
        model = await session.scalar(statement.limit(1))
        return _source_to_domain(model) if model else None

    async def list_versions(
        self,
        session: AsyncSession,
        source_id: UUID,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[SourceVersionRecord]:
        statement = (
            select(SourceVersion)
            .where(SourceVersion.source_id == source_id)
            .order_by(SourceVersion.created_at.desc(), SourceVersion.id.desc())
            .offset(offset)
        )
        if limit is not None:
            statement = statement.limit(limit)
        result = await session.scalars(statement)
        return [_version_to_domain(model) for model in result]

    async def count_versions(self, session: AsyncSession, source_id: UUID) -> int:
        return int(
            await session.scalar(
                select(func.count(SourceVersion.id)).where(SourceVersion.source_id == source_id)
            )
            or 0
        )

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
