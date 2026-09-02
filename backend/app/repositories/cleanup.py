from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.builds import TERMINAL_STATUSES
from app.domain.cleanup import (
    CleanupJobKind,
    CleanupJobRecord,
    CleanupJobStatus,
    CleanupTargetRecord,
    CleanupTargetStatus,
    CleanupTargetType,
)
from app.models.build import Build, BuildSourceVersion
from app.models.canonical import CanonicalSnapshot
from app.models.cleanup import CleanupJob, CleanupTarget
from app.models.deployment import Deployment
from app.models.indexing import DocumentIndexGeneration
from app.models.project import Project
from app.models.source import ProjectSource, SourceVersion

_TERMINAL_TARGETS = {
    CleanupTargetStatus.COMPLETED,
    CleanupTargetStatus.SKIPPED_REFERENCED,
    CleanupTargetStatus.FAILED,
}


async def lock_object_reference(session: AsyncSession, storage_key: str) -> None:
    """Serialize object reference creation with reference-aware external deletion."""
    await session.execute(
        select(
            func.pg_advisory_xact_lock(
                func.hashtextextended(f"mcplica:object-reference:{storage_key}", 0)
            )
        )
    )


async def lock_vector_reference(
    session: AsyncSession,
    *,
    collection_name: str,
    project_id: UUID,
    generation_id: UUID,
) -> None:
    """Serialize vector-generation publication with reference-aware deletion."""

    identity = f"{collection_name}:{project_id}:{generation_id}"
    await session.execute(
        select(
            func.pg_advisory_xact_lock(
                func.hashtextextended(f"mcplica:vector-reference:{identity}", 0)
            )
        )
    )


def _target_key(*parts: object) -> str:
    return hashlib.sha256("\x00".join(str(part) for part in parts).encode()).hexdigest()


def _to_target(model: CleanupTarget) -> CleanupTargetRecord:
    return CleanupTargetRecord(
        id=model.id,
        job_id=model.job_id,
        target_type=model.target_type,
        status=model.status,
        storage_key=model.storage_key,
        collection_name=model.collection_name,
        vector_project_id=model.vector_project_id,
        generation_id=model.generation_id,
        attempt_count=model.attempt_count,
        next_attempt_at=model.next_attempt_at,
        lease_expires_at=model.lease_expires_at,
        execution_token=model.execution_token,
        last_error_code=model.last_error_code,
        last_error_summary=model.last_error_summary,
    )


def _to_job(model: CleanupJob) -> CleanupJobRecord:
    return CleanupJobRecord(
        id=model.id,
        kind=model.kind,
        status=model.status,
        project_id=model.project_id,
        requested_by=model.requested_by,
        request_id=model.request_id,
        total_targets=model.total_targets,
        completed_targets=model.completed_targets,
        skipped_targets=model.skipped_targets,
        failed_targets=model.failed_targets,
        last_error_code=model.last_error_code,
        last_error_summary=model.last_error_summary,
        created_at=model.created_at,
        updated_at=model.updated_at,
        completed_at=model.completed_at,
    )


class CleanupRepository:
    async def create_job(
        self,
        session: AsyncSession,
        *,
        kind: CleanupJobKind,
        idempotency_key: str,
        project_id: UUID | None,
        requested_by: UUID | None,
        request_id: str | None,
    ) -> CleanupJobRecord:
        existing = await session.scalar(
            select(CleanupJob).where(CleanupJob.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return _to_job(existing)
        model = CleanupJob(
            id=uuid4(),
            kind=kind,
            status=CleanupJobStatus.PENDING,
            project_id=project_id,
            requested_by=requested_by,
            request_id=request_id,
            idempotency_key=idempotency_key,
            total_targets=0,
            completed_targets=0,
            skipped_targets=0,
            failed_targets=0,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _to_job(model)

    async def get_job(self, session: AsyncSession, job_id: UUID) -> CleanupJobRecord | None:
        model = await session.get(CleanupJob, job_id)
        return _to_job(model) if model is not None else None

    async def list_jobs(
        self,
        session: AsyncSession,
        *,
        project_id: UUID | None = None,
        limit: int = 100,
    ) -> list[CleanupJobRecord]:
        statement = select(CleanupJob)
        if project_id is not None:
            statement = statement.where(CleanupJob.project_id == project_id)
        models = await session.scalars(
            statement.order_by(CleanupJob.created_at.desc()).limit(limit)
        )
        return [_to_job(model) for model in models]

    async def add_object_target(
        self,
        session: AsyncSession,
        job_id: UUID,
        storage_key: str,
        *,
        not_before: datetime | None = None,
    ) -> None:
        key = _target_key(CleanupTargetType.OBJECT.value, storage_key)
        result = await session.execute(
            insert(CleanupTarget)
            .values(
                id=uuid4(),
                job_id=job_id,
                target_key=key,
                target_type=CleanupTargetType.OBJECT,
                status=CleanupTargetStatus.PENDING,
                storage_key=storage_key,
                attempt_count=0,
                next_attempt_at=not_before or datetime.now(UTC),
            )
            .on_conflict_do_nothing(constraint="uq_cleanup_targets_job_target_key")
            .returning(CleanupTarget.id)
        )
        if result.scalar_one_or_none() is not None:
            await session.execute(
                update(CleanupJob)
                .where(CleanupJob.id == job_id)
                .values(total_targets=CleanupJob.total_targets + 1)
            )

    async def add_vector_target(
        self,
        session: AsyncSession,
        job_id: UUID,
        *,
        collection_name: str,
        project_id: UUID,
        generation_id: UUID,
    ) -> None:
        key = _target_key(
            CleanupTargetType.VECTOR_GENERATION.value,
            collection_name,
            project_id,
            generation_id,
        )
        result = await session.execute(
            insert(CleanupTarget)
            .values(
                id=uuid4(),
                job_id=job_id,
                target_key=key,
                target_type=CleanupTargetType.VECTOR_GENERATION,
                status=CleanupTargetStatus.PENDING,
                collection_name=collection_name,
                vector_project_id=project_id,
                generation_id=generation_id,
                attempt_count=0,
                next_attempt_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(constraint="uq_cleanup_targets_job_target_key")
            .returning(CleanupTarget.id)
        )
        if result.scalar_one_or_none() is not None:
            await session.execute(
                update(CleanupJob)
                .where(CleanupJob.id == job_id)
                .values(total_targets=CleanupJob.total_targets + 1)
            )

    async def capture_project_targets(
        self,
        session: AsyncSession,
        job_id: UUID,
        project_id: UUID,
    ) -> None:
        source_keys = await session.scalars(
            select(SourceVersion.storage_key)
            .join(ProjectSource, ProjectSource.id == SourceVersion.source_id)
            .where(ProjectSource.project_id == project_id)
        )
        build_rows = await session.execute(
            select(Build.manifest_storage_key, Build.artifact_storage_key).where(
                Build.project_id == project_id
            )
        )
        generations = await session.scalars(
            select(DocumentIndexGeneration).where(DocumentIndexGeneration.project_id == project_id)
        )
        for storage_key in source_keys:
            await self.add_object_target(session, job_id, storage_key)
        for manifest_key, artifact_key in build_rows:
            for storage_key in (manifest_key, artifact_key):
                if storage_key is not None:
                    await self.add_object_target(session, job_id, storage_key)
        for generation in generations:
            if generation.chunk_manifest_storage_key is not None:
                await self.add_object_target(session, job_id, generation.chunk_manifest_storage_key)
            if generation.collection_name is not None:
                await self.add_vector_target(
                    session,
                    job_id,
                    collection_name=generation.collection_name,
                    project_id=generation.project_id,
                    generation_id=generation.id,
                )

    async def capture_source_targets(
        self,
        session: AsyncSession,
        job_id: UUID,
        source_id: UUID,
    ) -> None:
        keys = await session.scalars(
            select(SourceVersion.storage_key).where(SourceVersion.source_id == source_id)
        )
        for storage_key in keys:
            await self.add_object_target(session, job_id, storage_key)

    async def capture_build_targets(
        self,
        session: AsyncSession,
        job_id: UUID,
        builds: Iterable[Build],
    ) -> None:
        for build in builds:
            for storage_key in (build.manifest_storage_key, build.artifact_storage_key):
                if storage_key is not None:
                    await self.add_object_target(session, job_id, storage_key)
            generation = await session.scalar(
                select(DocumentIndexGeneration).where(DocumentIndexGeneration.build_id == build.id)
            )
            if generation is None:
                continue
            if generation.chunk_manifest_storage_key is not None:
                await self.add_object_target(session, job_id, generation.chunk_manifest_storage_key)
            if generation.collection_name is not None:
                await self.add_vector_target(
                    session,
                    job_id,
                    collection_name=generation.collection_name,
                    project_id=generation.project_id,
                    generation_id=generation.id,
                )

    async def capture_build_target(
        self,
        session: AsyncSession,
        job_id: UUID,
        build_id: UUID,
    ) -> None:
        build = await session.get(Build, build_id)
        if build is not None:
            await self.capture_build_targets(session, job_id, [build])

    async def finalize_empty_job(self, session: AsyncSession, job_id: UUID) -> None:
        now = datetime.now(UTC)
        await session.execute(
            update(CleanupJob)
            .where(CleanupJob.id == job_id, CleanupJob.total_targets == 0)
            .values(status=CleanupJobStatus.COMPLETED, completed_at=now)
        )

    async def claim_due_targets(
        self,
        session: AsyncSession,
        *,
        limit: int,
        lease_seconds: float,
        eligible_at: datetime | None = None,
    ) -> list[CleanupTargetRecord]:
        claim_time = datetime.now(UTC)
        eligibility_cutoff = eligible_at or claim_time
        due = (
            CleanupTarget.status.in_(
                {
                    CleanupTargetStatus.PENDING,
                    CleanupTargetStatus.RUNNING,
                    CleanupTargetStatus.RETRYING,
                }
            ),
            CleanupTarget.next_attempt_at <= eligibility_cutoff,
            or_(
                CleanupTarget.lease_expires_at.is_(None),
                CleanupTarget.lease_expires_at <= eligibility_cutoff,
            ),
        )
        models: list[CleanupTarget] = []
        while len(models) < limit:
            job_id = await session.scalar(
                select(CleanupJob.id)
                .join(CleanupTarget, CleanupTarget.job_id == CleanupJob.id)
                .where(*due)
                .order_by(CleanupTarget.next_attempt_at, CleanupTarget.created_at)
                .with_for_update(of=CleanupJob, skip_locked=True)
                .limit(1)
            )
            if job_id is None:
                break
            model = await session.scalar(
                select(CleanupTarget)
                .where(CleanupTarget.job_id == job_id, *due)
                .order_by(CleanupTarget.next_attempt_at, CleanupTarget.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if model is None:
                continue
            models.append(model)
            model.status = CleanupTargetStatus.RUNNING
            model.attempt_count += 1
            model.execution_token = uuid4()
            lease_expires_at = claim_time + timedelta(seconds=lease_seconds)
            model.lease_expires_at = lease_expires_at
            model.next_attempt_at = lease_expires_at
            model.last_error_code = None
            model.last_error_summary = None
            await session.execute(
                update(CleanupJob)
                .where(CleanupJob.id == job_id)
                .values(status=CleanupJobStatus.RUNNING, completed_at=None)
            )
        await session.flush()
        return [_to_target(model) for model in models]

    async def lock_claimed_target(
        self,
        session: AsyncSession,
        target_id: UUID,
        *,
        execution_token: UUID,
        attempt_count: int,
    ) -> CleanupTargetRecord | None:
        job_id = await session.scalar(
            select(CleanupTarget.job_id).where(CleanupTarget.id == target_id)
        )
        if job_id is None:
            return None
        await session.scalar(select(CleanupJob.id).where(CleanupJob.id == job_id).with_for_update())
        model = await session.scalar(
            select(CleanupTarget).where(CleanupTarget.id == target_id).with_for_update()
        )
        if (
            model is None
            or model.status is not CleanupTargetStatus.RUNNING
            or model.execution_token != execution_token
            or model.attempt_count != attempt_count
            or model.lease_expires_at is None
            or model.lease_expires_at <= datetime.now(UTC)
        ):
            return None
        return _to_target(model)

    async def object_is_referenced(self, session: AsyncSession, storage_key: str) -> bool:
        checks = (
            select(SourceVersion.id).where(SourceVersion.storage_key == storage_key).limit(1),
            select(Build.id)
            .where(
                or_(
                    Build.manifest_storage_key == storage_key,
                    Build.artifact_storage_key == storage_key,
                )
            )
            .limit(1),
            select(DocumentIndexGeneration.id)
            .where(DocumentIndexGeneration.chunk_manifest_storage_key == storage_key)
            .limit(1),
        )
        for statement in checks:
            if await session.scalar(statement) is not None:
                return True
        return False

    async def vector_is_referenced(
        self,
        session: AsyncSession,
        *,
        collection_name: str,
        project_id: UUID,
        generation_id: UUID,
    ) -> bool:
        return (
            await session.scalar(
                select(DocumentIndexGeneration.id)
                .where(
                    DocumentIndexGeneration.id == generation_id,
                    DocumentIndexGeneration.project_id == project_id,
                    DocumentIndexGeneration.collection_name == collection_name,
                )
                .limit(1)
            )
            is not None
        )

    async def mark_completed(
        self,
        session: AsyncSession,
        target_id: UUID,
        *,
        skipped_referenced: bool = False,
        execution_token: UUID | None = None,
        attempt_count: int | None = None,
    ) -> bool:
        model = await self._lock_job_and_target(session, target_id)
        if model is None or model.status in _TERMINAL_TARGETS:
            return False
        if model.status is CleanupTargetStatus.RUNNING and (
            execution_token is None
            or attempt_count is None
            or model.execution_token != execution_token
            or model.attempt_count != attempt_count
        ):
            return False
        model.status = (
            CleanupTargetStatus.SKIPPED_REFERENCED
            if skipped_referenced
            else CleanupTargetStatus.COMPLETED
        )
        model.lease_expires_at = None
        model.execution_token = None
        model.last_error_code = None
        model.last_error_summary = None
        await session.flush()
        await self._refresh_job(session, model.job_id)
        return True

    async def mark_failed(
        self,
        session: AsyncSession,
        target_id: UUID,
        *,
        error_code: str,
        error_summary: str,
        max_attempts: int,
        retry_delay_seconds: float,
        execution_token: UUID,
        attempt_count: int,
    ) -> bool:
        model = await self._lock_job_and_target(session, target_id)
        if (
            model is None
            or model.status is not CleanupTargetStatus.RUNNING
            or model.execution_token != execution_token
            or model.attempt_count != attempt_count
        ):
            return False
        terminal = model.attempt_count >= max_attempts
        model.status = CleanupTargetStatus.FAILED if terminal else CleanupTargetStatus.RETRYING
        model.lease_expires_at = None
        model.execution_token = None
        model.next_attempt_at = datetime.now(UTC) + timedelta(seconds=retry_delay_seconds)
        model.last_error_code = error_code[:128]
        model.last_error_summary = error_summary[:2_000]
        await session.flush()
        await self._refresh_job(session, model.job_id)
        return True

    async def _lock_job_and_target(
        self,
        session: AsyncSession,
        target_id: UUID,
    ) -> CleanupTarget | None:
        job_id = await session.scalar(
            select(CleanupTarget.job_id).where(CleanupTarget.id == target_id)
        )
        if job_id is None:
            return None
        await session.scalar(select(CleanupJob.id).where(CleanupJob.id == job_id).with_for_update())
        return await session.scalar(
            select(CleanupTarget).where(CleanupTarget.id == target_id).with_for_update()
        )

    async def make_job_due(self, session: AsyncSession, job_id: UUID) -> None:
        await session.execute(
            update(CleanupTarget)
            .where(
                CleanupTarget.job_id == job_id,
                CleanupTarget.status.in_(
                    {CleanupTargetStatus.PENDING, CleanupTargetStatus.RETRYING}
                ),
            )
            .values(next_attempt_at=datetime.now(UTC))
        )

    async def _refresh_job(self, session: AsyncSession, job_id: UUID) -> None:
        await session.scalar(select(CleanupJob.id).where(CleanupJob.id == job_id).with_for_update())
        rows = await session.execute(
            select(CleanupTarget.status, func.count(CleanupTarget.id))
            .where(CleanupTarget.job_id == job_id)
            .group_by(CleanupTarget.status)
        )
        counts = {status: count for status, count in rows}
        total = sum(counts.values())
        completed = counts.get(CleanupTargetStatus.COMPLETED, 0)
        skipped = counts.get(CleanupTargetStatus.SKIPPED_REFERENCED, 0)
        failed = counts.get(CleanupTargetStatus.FAILED, 0)
        retrying = counts.get(CleanupTargetStatus.RETRYING, 0)
        running = counts.get(CleanupTargetStatus.RUNNING, 0)
        terminal_count = completed + skipped + failed
        now = datetime.now(UTC)
        if total == terminal_count:
            status = CleanupJobStatus.FAILED if failed else CleanupJobStatus.COMPLETED
            completed_at = now
        elif retrying:
            status = CleanupJobStatus.RETRYING
            completed_at = None
        elif running:
            status = CleanupJobStatus.RUNNING
            completed_at = None
        else:
            status = CleanupJobStatus.PENDING
            completed_at = None
        error_target = await session.scalar(
            select(CleanupTarget)
            .where(
                CleanupTarget.job_id == job_id,
                CleanupTarget.last_error_code.is_not(None),
            )
            .order_by(CleanupTarget.updated_at.desc())
            .limit(1)
        )
        await session.execute(
            update(CleanupJob)
            .where(CleanupJob.id == job_id)
            .values(
                status=status,
                total_targets=total,
                completed_targets=completed,
                skipped_targets=skipped,
                failed_targets=failed,
                last_error_code=(
                    error_target.last_error_code if error_target is not None else None
                ),
                last_error_summary=(
                    error_target.last_error_summary if error_target is not None else None
                ),
                completed_at=completed_at,
            )
        )

    async def list_project_ids(self, session: AsyncSession) -> list[UUID]:
        return list(await session.scalars(select(Project.id).order_by(Project.id)))

    async def prepare_retention_job(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        build_retention_count: int | None,
        source_retention_days: int | None,
        now: datetime | None = None,
    ) -> CleanupJobRecord | None:
        project = await session.scalar(
            select(Project).where(Project.id == project_id).with_for_update(skip_locked=True)
        )
        if project is None:
            return None

        all_builds = list(
            await session.scalars(
                select(Build).where(Build.project_id == project_id).order_by(Build.sequence.desc())
            )
        )
        protected_build_ids = {
            build.id for build in all_builds[: build_retention_count or len(all_builds)]
        }
        protected_build_ids.update(
            build.id for build in all_builds if build.status not in TERMINAL_STATUSES
        )
        if project.active_build_id is not None:
            protected_build_ids.add(project.active_build_id)
        protected_build_ids.update(
            await session.scalars(
                select(Deployment.build_id).where(Deployment.project_id == project_id)
            )
        )
        build_candidates = [
            build
            for build in all_builds
            if build_retention_count is not None
            and build.status in TERMINAL_STATUSES
            and build.id not in protected_build_ids
        ]
        build_candidate_ids = {build.id for build in build_candidates}

        version_candidates: list[SourceVersion] = []
        if source_retention_days is not None:
            cutoff = (now or datetime.now(UTC)) - timedelta(days=source_retention_days)
            sources = await session.scalars(
                select(ProjectSource.id).where(ProjectSource.project_id == project_id)
            )
            for source_id in sources:
                versions = list(
                    await session.scalars(
                        select(SourceVersion)
                        .where(SourceVersion.source_id == source_id)
                        .order_by(SourceVersion.created_at.desc(), SourceVersion.id.desc())
                    )
                )
                for version in versions[1:]:
                    if version.created_at >= cutoff:
                        continue
                    remaining_reference_query = select(BuildSourceVersion.build_id).where(
                        BuildSourceVersion.source_version_id == version.id
                    )
                    if build_candidate_ids:
                        remaining_reference_query = remaining_reference_query.where(
                            BuildSourceVersion.build_id.not_in(build_candidate_ids)
                        )
                    remaining_reference = await session.scalar(remaining_reference_query.limit(1))
                    if remaining_reference is None:
                        version_candidates.append(version)

        if not build_candidates and not version_candidates:
            return None
        identity = _target_key(
            project_id,
            *(sorted(str(build.id) for build in build_candidates)),
            *(sorted(str(version.id) for version in version_candidates)),
        )
        job = await self.create_job(
            session,
            kind=CleanupJobKind.RETENTION,
            idempotency_key=f"retention:{project_id}:{identity}",
            project_id=project_id,
            requested_by=None,
            request_id=None,
        )
        await self.capture_build_targets(session, job.id, build_candidates)
        for version in version_candidates:
            await self.add_object_target(session, job.id, version.storage_key)

        snapshot_ids = {
            build.canonical_snapshot_id
            for build in build_candidates
            if build.canonical_snapshot_id is not None
        }
        if build_candidate_ids:
            await session.execute(delete(Build).where(Build.id.in_(build_candidate_ids)))
        if version_candidates:
            await session.execute(
                delete(SourceVersion).where(
                    SourceVersion.id.in_({version.id for version in version_candidates})
                )
            )
        if snapshot_ids:
            await session.execute(
                delete(CanonicalSnapshot).where(
                    CanonicalSnapshot.id.in_(snapshot_ids),
                    ~select(Build.id)
                    .where(Build.canonical_snapshot_id == CanonicalSnapshot.id)
                    .exists(),
                )
            )
        await self.finalize_empty_job(session, job.id)
        refreshed = await self.get_job(session, job.id)
        assert refreshed is not None
        return refreshed
