from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from mcp_contracts.json_types import JsonObject
from pydantic import TypeAdapter
from sqlalchemy import CursorResult, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, InvalidStateError
from app.domain.builds import (
    TERMINAL_STATUSES,
    BuildAIRunRecord,
    BuildConfiguration,
    BuildRecord,
    BuildStatus,
    BuildTrigger,
    next_status,
)
from app.models.build import Build, BuildAIRun, BuildSourceVersion
from app.models.indexing import DocumentIndexGeneration
from app.models.project import Project
from app.repositories.cleanup import lock_object_reference

_JSON_OBJECT: TypeAdapter[JsonObject] = TypeAdapter(JsonObject)


def _release_admission_values(now: datetime) -> dict[str, object | None]:
    return {
        "admission_token": None,
        "admission_enqueued_at": None,
        "admission_heartbeat_at": None,
        "admission_lease_expires_at": None,
        "admission_released_at": now,
    }


def _to_domain(model: Build) -> BuildRecord:
    config = BuildConfiguration.model_validate(model.build_config_json)
    return BuildRecord(
        id=model.id,
        project_id=model.project_id,
        sequence=model.sequence,
        status=model.status,
        pipeline_stage=model.pipeline_stage,
        trigger=model.trigger,
        executable_configuration_sha256=(config.executable_configuration_sha256),
        canonical_snapshot_id=model.canonical_snapshot_id,
        previous_build_id=model.previous_build_id,
        compiler_version=model.compiler_version,
        manifest_schema_version=model.manifest_schema_version,
        runtime_compatibility=model.runtime_compatibility,
        analysis_model=model.analysis_model,
        validation_model=model.validation_model,
        embedding_model=model.embedding_model,
        embedding_dimensions=model.embedding_dimensions,
        prompt_bundle_version=model.prompt_bundle_version,
        enrichment_sha256=model.enrichment_sha256,
        manifest_sha256=model.manifest_sha256,
        artifact_sha256=model.artifact_sha256,
        manifest_storage_key=model.manifest_storage_key,
        artifact_storage_key=model.artifact_storage_key,
        error_code=model.error_code,
        error_summary=model.error_summary,
        requested_by=model.requested_by,
        created_at=model.created_at,
        started_at=model.started_at,
        completed_at=model.completed_at,
        cancellation_requested_at=model.cancellation_requested_at,
        cancellation_requested_by=model.cancellation_requested_by,
        cancellation_acknowledged_at=model.cancellation_acknowledged_at,
        admission_token=model.admission_token,
        admission_acquired_at=model.admission_acquired_at,
        admission_enqueued_at=model.admission_enqueued_at,
        admission_heartbeat_at=model.admission_heartbeat_at,
        admission_lease_expires_at=model.admission_lease_expires_at,
        admission_released_at=model.admission_released_at,
        admission_attempt_count=model.admission_attempt_count,
    )


def _ai_to_domain(model: BuildAIRun) -> BuildAIRunRecord:
    return BuildAIRunRecord(
        id=model.id,
        build_id=model.build_id,
        run_key=model.run_key,
        stage=model.stage,
        operation_key=model.operation_key,
        provider=model.provider,
        model=model.model,
        prompt_template_id=model.prompt_template_id,
        prompt_template_version=model.prompt_template_version,
        input_context_sha256=model.input_context_sha256,
        retrieved_chunk_ids=model.retrieved_chunk_ids,
        response_schema_id=model.response_schema_id,
        response_sha256=model.response_sha256,
        response=(
            _JSON_OBJECT.validate_python(model.response_json)
            if model.response_json is not None
            else None
        ),
        usage=model.usage_json,
        cost=model.cost_json,
        latency_ms=model.latency_ms,
        status=model.status,
        error_code=model.error_code,
        created_at=model.created_at,
    )


class BuildRepository:
    async def lock_project(self, session: AsyncSession, project_id: UUID) -> Project | None:
        return await session.scalar(
            select(Project).where(Project.id == project_id).with_for_update()
        )

    async def active_for_project(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> BuildRecord | None:
        model = await session.scalar(
            select(Build).where(
                Build.project_id == project_id,
                Build.status.not_in(TERMINAL_STATUSES),
            )
        )
        return _to_domain(model) if model else None

    async def get_many_with_configs(
        self,
        session: AsyncSession,
        build_ids: list[UUID],
    ) -> dict[UUID, tuple[BuildRecord, BuildConfiguration]]:
        """Load bounded build metadata without one query per source summary."""
        if not build_ids:
            return {}
        models = list(await session.scalars(select(Build).where(Build.id.in_(set(build_ids)))))
        return {
            model.id: (
                _to_domain(model),
                BuildConfiguration.model_validate(model.build_config_json),
            )
            for model in models
        }

    async def latest_ready(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> BuildRecord | None:
        model = await session.scalar(
            select(Build)
            .where(Build.project_id == project_id, Build.status == BuildStatus.READY)
            .order_by(Build.sequence.desc())
            .limit(1)
        )
        return _to_domain(model) if model else None

    async def latest_with_canonical_snapshot(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> BuildRecord | None:
        model = await session.scalar(
            select(Build)
            .where(
                Build.project_id == project_id,
                Build.canonical_snapshot_id.is_not(None),
            )
            .order_by(Build.sequence.desc())
            .limit(1)
        )
        return _to_domain(model) if model else None

    async def latest_for_source_version(
        self,
        session: AsyncSession,
        source_version_id: UUID,
    ) -> BuildRecord | None:
        model = await session.scalar(
            select(Build)
            .join(BuildSourceVersion, BuildSourceVersion.build_id == Build.id)
            .where(BuildSourceVersion.source_version_id == source_version_id)
            .order_by(Build.sequence.desc())
            .limit(1)
        )
        return _to_domain(model) if model else None

    async def list_all(
        self,
        session: AsyncSession,
        *,
        project_id: UUID | None = None,
        status: BuildStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BuildRecord]:
        statement = select(Build)
        if project_id is not None:
            statement = statement.where(Build.project_id == project_id)
        if status is not None:
            statement = statement.where(Build.status == status)
        result = await session.scalars(
            statement.order_by(Build.created_at.desc()).limit(min(limit, 500)).offset(offset)
        )
        return [_to_domain(model) for model in result]

    async def count_all(
        self,
        session: AsyncSession,
        *,
        project_id: UUID | None = None,
        status: BuildStatus | None = None,
    ) -> int:
        statement = select(func.count(Build.id))
        if project_id is not None:
            statement = statement.where(Build.project_id == project_id)
        if status is not None:
            statement = statement.where(Build.status == status)
        return int(await session.scalar(statement) or 0)

    async def status_counts(
        self,
        session: AsyncSession,
        *,
        project_id: UUID | None = None,
    ) -> dict[BuildStatus, int]:
        statement = select(Build.status, func.count(Build.id))
        if project_id is not None:
            statement = statement.where(Build.project_id == project_id)
        rows = await session.execute(statement.group_by(Build.status))
        return {status: int(count) for status, count in rows.tuples()}

    async def create(
        self,
        session: AsyncSession,
        *,
        build_id: UUID,
        project_id: UUID,
        trigger: BuildTrigger,
        source_version_ids: list[UUID],
        requested_by: UUID,
        compiler_version: str,
        runtime_compatibility: str,
        analysis_model: str,
        validation_model: str,
        embedding_model: str | None,
        prompt_bundle_version: str,
        build_config: dict[str, object],
    ) -> BuildRecord:
        if await self.active_for_project(session, project_id):
            raise ConflictError("The Project already has an active Build")
        sequence = (
            int(
                await session.scalar(
                    select(func.coalesce(func.max(Build.sequence), 0)).where(
                        Build.project_id == project_id
                    )
                )
                or 0
            )
            + 1
        )
        previous = await session.scalar(
            select(Build.id)
            .where(Build.project_id == project_id, Build.status == BuildStatus.READY)
            .order_by(Build.sequence.desc())
            .limit(1)
        )
        model = Build(
            id=build_id,
            project_id=project_id,
            sequence=sequence,
            status=BuildStatus.QUEUED,
            pipeline_stage=BuildStatus.QUEUED,
            trigger=trigger,
            previous_build_id=previous,
            compiler_version=compiler_version,
            manifest_schema_version="mcp-manifest/v1",
            runtime_compatibility=runtime_compatibility,
            analysis_model=analysis_model,
            validation_model=validation_model,
            embedding_model=embedding_model,
            prompt_bundle_version=prompt_bundle_version,
            build_config_json=build_config,
            requested_by=requested_by,
        )
        session.add(model)
        session.add_all(
            BuildSourceVersion(build_id=build_id, source_version_id=source_id)
            for source_id in sorted(source_version_ids, key=str)
        )
        await session.flush()
        await session.refresh(model)
        return _to_domain(model)

    async def get(self, session: AsyncSession, build_id: UUID) -> BuildRecord | None:
        model = await session.get(Build, build_id)
        return _to_domain(model) if model else None

    async def list_for_project(
        self,
        session: AsyncSession,
        project_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BuildRecord]:
        result = await session.scalars(
            select(Build)
            .where(Build.project_id == project_id)
            .order_by(Build.sequence.desc())
            .limit(min(limit, 500))
            .offset(offset)
        )
        return [_to_domain(model) for model in result]

    async def source_version_ids(
        self,
        session: AsyncSession,
        build_id: UUID,
    ) -> list[UUID]:
        values = await session.scalars(
            select(BuildSourceVersion.source_version_id)
            .where(BuildSourceVersion.build_id == build_id)
            .order_by(BuildSourceVersion.source_version_id)
        )
        return list(values)

    async def transition(
        self,
        session: AsyncSession,
        build_id: UUID,
        *,
        expected: BuildStatus,
        target: BuildStatus,
    ) -> BuildRecord:
        if next_status(expected) is not target:
            raise InvalidStateError(
                f"Build transition {expected.value} -> {target.value} is not monotonic"
            )
        values: dict[str, object] = {"status": target, "pipeline_stage": target}
        now = datetime.now(UTC)
        if expected is BuildStatus.QUEUED:
            values["started_at"] = now
        if target in TERMINAL_STATUSES:
            values["completed_at"] = now
            values.update(_release_admission_values(now))
        result = cast(
            CursorResult[Any],
            await session.execute(
                update(Build)
                .where(
                    Build.id == build_id,
                    Build.status == expected,
                    Build.cancellation_requested_at.is_(None),
                )
                .values(**values)
            ),
        )
        if result.rowcount != 1:
            raise InvalidStateError(
                f"Build did not transition from {expected.value} to {target.value}"
            )
        model = await session.get(Build, build_id)
        assert model is not None
        return _to_domain(model)

    async def set_canonical_snapshot(
        self,
        session: AsyncSession,
        build_id: UUID,
        snapshot_id: UUID,
    ) -> None:
        await self._stage_update(
            session,
            build_id,
            status=BuildStatus.PARSING,
            canonical_snapshot_id=snapshot_id,
        )

    async def set_embedding_metadata(
        self,
        session: AsyncSession,
        build_id: UUID,
        *,
        model: str | None,
        dimensions: int,
    ) -> None:
        await self._stage_update(
            session,
            build_id,
            status=BuildStatus.INDEXING,
            embedding_model=model,
            embedding_dimensions=dimensions,
        )

    async def set_enrichment(
        self,
        session: AsyncSession,
        build_id: UUID,
        *,
        enrichment: dict[str, object],
        enrichment_sha256: str,
    ) -> None:
        await self._stage_update(
            session,
            build_id,
            status=BuildStatus.ANALYZING,
            enrichment_json=enrichment,
            enrichment_sha256=enrichment_sha256,
        )

    async def get_enrichment(
        self,
        session: AsyncSession,
        build_id: UUID,
    ) -> dict[str, object] | None:
        model = await session.get(Build, build_id)
        return model.enrichment_json if model else None

    async def get_build_config(
        self,
        session: AsyncSession,
        build_id: UUID,
    ) -> BuildConfiguration | None:
        model = await session.get(Build, build_id)
        return BuildConfiguration.model_validate(model.build_config_json) if model else None

    async def set_manifest(
        self,
        session: AsyncSession,
        build_id: UUID,
        *,
        manifest_sha256: str,
        manifest_storage_key: str,
    ) -> None:
        await lock_object_reference(session, manifest_storage_key)
        await self._stage_update(
            session,
            build_id,
            status=BuildStatus.COMPILING,
            manifest_sha256=manifest_sha256,
            manifest_storage_key=manifest_storage_key,
        )

    async def set_artifact(
        self,
        session: AsyncSession,
        build_id: UUID,
        *,
        artifact_sha256: str,
        artifact_storage_key: str,
    ) -> None:
        await lock_object_reference(session, artifact_storage_key)
        await self._stage_update(
            session,
            build_id,
            status=BuildStatus.PACKAGING,
            artifact_sha256=artifact_sha256,
            artifact_storage_key=artifact_storage_key,
        )

    async def fail(
        self,
        session: AsyncSession,
        build_id: UUID,
        *,
        error_code: str,
        error_summary: str,
    ) -> None:
        now = datetime.now(UTC)
        await session.execute(
            update(Build)
            .where(
                Build.id == build_id,
                Build.status.not_in(TERMINAL_STATUSES),
                Build.cancellation_requested_at.is_(None),
            )
            .values(
                status=BuildStatus.FAILED,
                error_code=error_code[:128],
                error_summary=error_summary[:1000],
                completed_at=now,
                **_release_admission_values(now),
            )
        )

    async def mark_ready(self, session: AsyncSession, build_id: UUID) -> BuildRecord:
        return await self.transition(
            session,
            build_id,
            expected=BuildStatus.PACKAGING,
            target=BuildStatus.READY,
        )

    async def request_cancellation(
        self,
        session: AsyncSession,
        build_id: UUID,
        *,
        requested_by: UUID,
    ) -> BuildRecord:
        model = await session.scalar(select(Build).where(Build.id == build_id).with_for_update())
        if model is None:
            raise InvalidStateError("Build is unavailable")
        if model.status in TERMINAL_STATUSES:
            raise InvalidStateError("Only an active Build can be cancelled")
        if model.cancellation_requested_at is None:
            model.cancellation_requested_at = datetime.now(UTC)
            model.cancellation_requested_by = requested_by
            await session.flush()
            await session.refresh(model)
        return _to_domain(model)

    async def cancellation_requested(self, session: AsyncSession, build_id: UUID) -> bool:
        requested_at = await session.scalar(
            select(Build.cancellation_requested_at).where(Build.id == build_id)
        )
        return requested_at is not None

    async def acknowledge_cancellation(self, session: AsyncSession, build_id: UUID) -> BuildRecord:
        now = datetime.now(UTC)
        result = cast(
            CursorResult[Any],
            await session.execute(
                update(Build)
                .where(
                    Build.id == build_id,
                    Build.status.not_in(TERMINAL_STATUSES),
                    Build.cancellation_requested_at.is_not(None),
                )
                .values(
                    status=BuildStatus.CANCELLED,
                    completed_at=now,
                    cancellation_acknowledged_at=now,
                    manifest_sha256=None,
                    manifest_storage_key=None,
                    artifact_sha256=None,
                    artifact_storage_key=None,
                    **_release_admission_values(now),
                )
            ),
        )
        if result.rowcount != 1:
            model = await session.get(Build, build_id)
            if model is not None and model.status is BuildStatus.CANCELLED:
                return _to_domain(model)
            raise InvalidStateError("Build cancellation is not pending acknowledgement")
        await session.execute(
            delete(DocumentIndexGeneration).where(DocumentIndexGeneration.build_id == build_id)
        )
        model = await session.get(Build, build_id)
        assert model is not None
        return _to_domain(model)

    async def _stage_update(
        self,
        session: AsyncSession,
        build_id: UUID,
        *,
        status: BuildStatus,
        **values: object,
    ) -> None:
        result = cast(
            CursorResult[Any],
            await session.execute(
                update(Build)
                .where(
                    Build.id == build_id,
                    Build.status == status,
                    Build.cancellation_requested_at.is_(None),
                )
                .values(**values)
            ),
        )
        if result.rowcount != 1:
            raise InvalidStateError(f"Build is not in {status.value}")


class BuildAIRunRepository:
    async def get_by_run_key(
        self,
        session: AsyncSession,
        *,
        build_id: UUID,
        run_key: str,
    ) -> BuildAIRunRecord | None:
        model = await session.scalar(
            select(BuildAIRun).where(
                BuildAIRun.build_id == build_id,
                BuildAIRun.run_key == run_key,
            )
        )
        return _ai_to_domain(model) if model else None

    async def list_for_build(
        self,
        session: AsyncSession,
        build_id: UUID,
    ) -> list[BuildAIRunRecord]:
        result = await session.scalars(
            select(BuildAIRun)
            .where(BuildAIRun.build_id == build_id)
            .order_by(BuildAIRun.created_at.asc(), BuildAIRun.id.asc())
        )
        return [_ai_to_domain(model) for model in result]

    async def create(
        self,
        session: AsyncSession,
        *,
        build_id: UUID,
        run_key: str,
        stage: str,
        operation_key: str | None,
        model: str,
        prompt_template_id: str,
        prompt_template_version: str,
        input_context_sha256: str,
        retrieved_chunk_ids: list[str],
        response_schema_id: str,
        response_sha256: str | None,
        response_json: dict[str, object] | None,
        usage: dict[str, Any] | None,
        cost: dict[str, Any] | None,
        latency_ms: int | None,
        status: str,
        error_code: str | None = None,
    ) -> BuildAIRunRecord:
        model_record = await session.scalar(
            select(BuildAIRun).where(
                BuildAIRun.build_id == build_id,
                BuildAIRun.run_key == run_key,
            )
        )
        if model_record is not None and model_record.status == "succeeded":
            return _ai_to_domain(model_record)
        values: dict[str, object] = {
            "stage": stage,
            "operation_key": operation_key,
            "provider": "openrouter",
            "model": model,
            "prompt_template_id": prompt_template_id,
            "prompt_template_version": prompt_template_version,
            "input_context_sha256": input_context_sha256,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "response_schema_id": response_schema_id,
            "response_sha256": response_sha256,
            "response_json": response_json,
            "usage_json": usage,
            "cost_json": cost,
            "latency_ms": latency_ms,
            "status": status,
            "error_code": error_code,
        }
        if model_record is None:
            model_record = BuildAIRun(build_id=build_id, run_key=run_key, **values)
            session.add(model_record)
        else:
            for name, value in values.items():
                setattr(model_record, name, value)
        await session.flush()
        await session.refresh(model_record)
        return _ai_to_domain(model_record)
