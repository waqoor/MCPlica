import asyncio
import hashlib
import json
import time
from typing import cast
from uuid import UUID

from mcp_contracts import CanonicalApi, MCPManifest
from mcp_contracts.json_types import JsonObject

from app.clients.database import DatabaseClient
from app.compilers.mcp.compiler import compile_manifest
from app.core.canonical_json import canonical_sha256
from app.core.exceptions import InvalidStateError, MCPlicaError, NotFoundError, SourceParseError
from app.core.redaction import redact
from app.domain.analysis import EnrichmentSnapshot, OperationEnrichment
from app.domain.builds import (
    TERMINAL_STATUSES,
    BuildConfiguration,
    BuildRecord,
    BuildStatus,
    BuildTrigger,
)
from app.domain.cleanup import CleanupJobKind
from app.domain.indexing import DocumentIndexGenerationRecord
from app.domain.projects import ProjectRoutingConfiguration
from app.domain.sources import BoundSourceVersionRecord
from app.domain.validation import ValidationStatus
from app.observability import observe_build_stage, observe_generated_operations
from app.prompts import OPERATION_ENRICHMENT_PROMPT
from app.providers.storage import ArtifactStorage
from app.repositories.audit import AuditRepository
from app.repositories.builds import BuildRepository
from app.repositories.cleanup import CleanupRepository
from app.repositories.indexing import IndexGenerationRepository
from app.repositories.projects import ProjectRepository
from app.repositories.sources import SourceRepository
from app.repositories.validation import ValidationRepository
from app.services.analysis import AnalysisService
from app.services.analysis.reuse import select_reusable_enrichment
from app.services.artifacts import ArtifactService
from app.services.builds.credential_mapping import map_credentials
from app.services.canonicalization import CanonicalizationService
from app.services.indexing import IndexingService
from app.services.validation import ValidationService


class BuildCancellationRequested(Exception):
    """Internal cooperative signal converted into durable CANCELLED state."""


class BuildPipeline:
    """Retry-safe monotonic pipeline. PostgreSQL remains authoritative at every boundary."""

    def __init__(
        self,
        database: DatabaseClient,
        builds: BuildRepository,
        projects: ProjectRepository,
        sources: SourceRepository,
        generations: IndexGenerationRepository,
        reports: ValidationRepository,
        audit: AuditRepository,
        storage: ArtifactStorage,
        canonicalization: CanonicalizationService,
        indexing: IndexingService,
        analysis: AnalysisService,
        validation: ValidationService,
        artifacts: ArtifactService,
        cleanup: CleanupRepository | None = None,
    ) -> None:
        self._database = database
        self._builds = builds
        self._projects = projects
        self._sources = sources
        self._generations = generations
        self._reports = reports
        self._audit = audit
        self._storage = storage
        self._canonicalization = canonicalization
        self._indexing = indexing
        self._analysis = analysis
        self._validation = validation
        self._artifacts = artifacts
        self._cleanup = cleanup

    async def run(self, build_id: UUID) -> BuildRecord:
        while True:
            build = await self._get(build_id)
            if build.status in TERMINAL_STATUSES:
                return build
            started = time.perf_counter()
            stage_outcome = "failed"
            try:
                await self._cancellation_checkpoint(build.id)
                if build.status is BuildStatus.QUEUED:
                    await self._transition(build_id, BuildStatus.QUEUED, BuildStatus.INGESTING)
                elif build.status is BuildStatus.INGESTING:
                    await self._verify_bound_sources(build)
                    await self._transition(build_id, BuildStatus.INGESTING, BuildStatus.PARSING)
                elif build.status is BuildStatus.PARSING:
                    await self._canonicalize(build)
                    await self._transition(build_id, BuildStatus.PARSING, BuildStatus.INDEXING)
                elif build.status is BuildStatus.INDEXING:
                    await self._index(build)
                    await self._transition(build_id, BuildStatus.INDEXING, BuildStatus.ANALYZING)
                elif build.status is BuildStatus.ANALYZING:
                    await self._analyze(build)
                    await self._transition(build_id, BuildStatus.ANALYZING, BuildStatus.COMPILING)
                elif build.status is BuildStatus.COMPILING:
                    await self._compile(build)
                    await self._transition(build_id, BuildStatus.COMPILING, BuildStatus.VALIDATING)
                elif build.status is BuildStatus.VALIDATING:
                    passed = await self._validate(build)
                    if not passed:
                        result = await self.fail(
                            build.id,
                            code="VALIDATION_FAILED",
                            summary="Build validation contains blocking findings",
                        )
                        stage_outcome = "succeeded"
                        return result
                    await self._transition(build_id, BuildStatus.VALIDATING, BuildStatus.PACKAGING)
                elif build.status is BuildStatus.PACKAGING:
                    await self._package(build)
                    result = await self._ready(build_id)
                    stage_outcome = "succeeded"
                    return result
                else:
                    raise InvalidStateError(f"Unhandled Build state {build.status.value}")
                stage_outcome = "succeeded"
            except BuildCancellationRequested:
                stage_outcome = "cancelled"
                return await self._acknowledge_cancellation(build.id)
            except InvalidStateError:
                current = await self._get(build_id)
                if current.status is BuildStatus.CANCELLED:
                    stage_outcome = "cancelled"
                    return current
                if current.cancellation_requested_at is not None:
                    stage_outcome = "cancelled"
                    return await self._acknowledge_cancellation(build.id)
                raise
            finally:
                observe_build_stage(
                    build.status.value.lower(),
                    stage_outcome,
                    time.perf_counter() - started,
                )

    async def fail(
        self,
        build_id: UUID,
        *,
        code: str,
        summary: str,
    ) -> BuildRecord:
        async with self._database.session_scope() as session:
            build = await self._builds.get(session, build_id)
            if build is None:
                raise NotFoundError("Build was not found")
            if build.status not in TERMINAL_STATUSES:
                await self._builds.fail(
                    session,
                    build_id,
                    error_code=code,
                    error_summary=summary,
                )
                await self._audit.append(
                    session,
                    actor_user_id=build.requested_by,
                    event_type="build.failed",
                    entity_type="build",
                    entity_id=build.id,
                    project_id=build.project_id,
                    metadata={"error_code": code, "stage": build.status.value},
                )
            failed = await self._builds.get(session, build_id)
            assert failed is not None
            return failed

    async def fail_from_exception(self, build_id: UUID, exc: Exception) -> BuildRecord:
        if isinstance(exc, MCPlicaError):
            return await self.fail(build_id, code=exc.code, summary=str(exc))
        return await self.fail(
            build_id,
            code="UNEXPECTED_BUILD_ERROR",
            summary="Build failed due to an unexpected internal error",
        )

    async def record_attempt_failure(
        self,
        build_id: UUID,
        exc: Exception,
        *,
        attempt_number: int,
        retry_scheduled: bool,
    ) -> None:
        error_code = exc.code if isinstance(exc, MCPlicaError) else "UNEXPECTED_BUILD_ERROR"
        async with self._database.session_scope() as session:
            build = await self._builds.get(session, build_id)
            if build is None:
                raise NotFoundError("Build was not found")
            await self._audit.append(
                session,
                actor_user_id=build.requested_by,
                event_type="build.attempt_failed",
                entity_type="build",
                entity_id=build.id,
                project_id=build.project_id,
                metadata={
                    "attempt_number": attempt_number,
                    "error_code": error_code,
                    "failure_category": type(exc).__name__,
                    "retry_scheduled": retry_scheduled,
                    "stage": build.status.value,
                },
            )

    async def _verify_bound_sources(self, build: BuildRecord) -> None:
        source_version_ids = await self._source_version_ids(build.id)
        async with self._database.session_scope() as session:
            bindings = await self._sources.list_bound_versions(
                session,
                build.project_id,
                source_version_ids,
            )
        if len(bindings) != len(source_version_ids):
            raise InvalidStateError("One or more bound source versions are unavailable")
        semaphore = asyncio.Semaphore(8)

        async def verify(binding: BoundSourceVersionRecord) -> None:
            await self._cancellation_checkpoint(build.id)
            async with semaphore:
                value = await self._storage.get(
                    binding.version.storage_key,
                    max_bytes=max(1, binding.version.byte_size),
                )
            await self._cancellation_checkpoint(build.id)
            if len(value) != binding.version.byte_size:
                raise InvalidStateError("Bound source byte size no longer matches metadata")
            if hashlib.sha256(value).hexdigest() != binding.version.content_sha256:
                raise InvalidStateError("Bound source content hash verification failed")

        await asyncio.gather(*(verify(binding) for binding in bindings))

    async def _canonicalize(self, build: BuildRecord) -> None:
        config = await self._config(build.id)
        if build.canonical_snapshot_id is None:
            source_version_ids = await self._source_version_ids(build.id)
            try:
                await self._cancellation_checkpoint(build.id)
                snapshot = await self._canonicalization.create_snapshot(
                    build.project_id,
                    source_version_ids,
                    max_source_bytes=config.source_max_bytes,
                    routing=ProjectRoutingConfiguration(
                        default_base_url=config.default_base_url,
                        active_server_ref=config.active_server_ref,
                        server_mappings=config.server_mappings,
                    ),
                )
                await self._cancellation_checkpoint(build.id)
            except SourceParseError as exc:
                await self._record_source_finding(build, exc, stage="parsing")
                raise
            async with self._database.session_scope() as session:
                await self._builds.set_canonical_snapshot(session, build.id, snapshot.id)
        else:
            snapshot = await self._canonicalization.get_snapshot(build.canonical_snapshot_id)
        if len(snapshot.canonical.operations) > config.max_operations:
            raise InvalidStateError(
                "Canonical operation count exceeds the Build's frozen configured limit"
            )
        if set(snapshot.source_version_ids) != set(await self._source_version_ids(build.id)):
            raise InvalidStateError("Canonical snapshot source bindings do not match the Build")

    async def _record_source_finding(
        self,
        build: BuildRecord,
        exc: SourceParseError,
        *,
        stage: str,
    ) -> None:
        raw_source_version_id = exc.details.get("source_version_id")
        try:
            source_version_id = UUID(str(raw_source_version_id))
        except (TypeError, ValueError):
            # Build topology errors have no single source owner and remain aggregate-only.
            return
        if source_version_id not in set(await self._source_version_ids(build.id)):
            raise InvalidStateError("Source finding identity is not bound to the Build")

        pointer_value = next(
            (
                exc.details[key]
                for key in ("source_pointer", "source_location", "pointer")
                if isinstance(exc.details.get(key), str) and exc.details[key]
            ),
            None,
        )

        def positive_position(key: str) -> int | None:
            value = exc.details.get(key)
            return (
                value
                if isinstance(value, int) and not isinstance(value, bool) and value >= 1
                else None
            )

        safe_details = redact(exc.details)
        encoded_details = json.dumps(
            safe_details,
            default=lambda _value: "[UNSERIALIZABLE]",
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        if len(encoded_details.encode("utf-8")) > 16_384:
            safe_details = {
                "details_truncated": True,
                "source_version_id": str(source_version_id),
                **({"source_pointer": pointer_value} if pointer_value else {}),
            }
        else:
            safe_details = json.loads(encoded_details)
        assert isinstance(safe_details, dict)
        typed_safe_details = cast(JsonObject, safe_details)

        async with self._database.session_scope() as session:
            await self._sources.upsert_finding(
                session,
                build_id=build.id,
                source_version_id=source_version_id,
                stage=stage,
                code=exc.code,
                severity="error",
                message=str(exc)[:4_000],
                pointer=pointer_value,
                line=positive_position("line"),
                column=positive_position("column"),
                details=typed_safe_details,
            )

    async def _index(self, build: BuildRecord) -> None:
        config = await self._config(build.id)
        if build.canonical_snapshot_id is None:
            raise InvalidStateError("Build has no canonical snapshot")
        snapshot = await self._canonicalization.get_snapshot(build.canonical_snapshot_id)
        generation = await self._indexing.index(
            project_id=build.project_id,
            build_id=build.id,
            source_version_ids=await self._source_version_ids(build.id),
            canonical=snapshot.canonical,
            embedding_model=build.embedding_model,
            config=config,
            cancellation_check=lambda: self._cancellation_checkpoint(build.id),
        )
        async with self._database.session_scope() as session:
            await self._builds.set_embedding_metadata(
                session,
                build.id,
                model=generation.embedding_model,
                dimensions=generation.dimensions or 0,
            )

    async def _analyze(self, build: BuildRecord) -> None:
        if build.enrichment_sha256 is not None:
            enrichment = await self._enrichment(build.id)
            if canonical_sha256(enrichment) != build.enrichment_sha256:
                raise InvalidStateError("Stored semantic enrichment hash verification failed")
            return
        if build.canonical_snapshot_id is None or not build.analysis_model:
            raise InvalidStateError("Build analysis inputs are incomplete")
        snapshot = await self._canonicalization.get_snapshot(build.canonical_snapshot_id)
        generation = await self._generation(build.id)
        config = await self._config(build.id)
        enrichment = await self._analysis.analyze(
            build_id=build.id,
            canonical=snapshot.canonical,
            generation=generation,
            model=build.analysis_model,
            include_documentation=config.include_documentation_in_analysis,
            max_context_chars=config.max_context_chars,
            max_concurrency=config.max_ai_concurrency,
            retrieval_top_k=config.retrieval_top_k,
            reusable=await self._reusable_enrichment(
                build,
                snapshot.canonical,
                generation,
                config,
            ),
            cancellation_check=lambda: self._cancellation_checkpoint(build.id),
        )
        digest = canonical_sha256(enrichment)
        async with self._database.session_scope() as session:
            await self._builds.set_enrichment(
                session,
                build.id,
                enrichment=enrichment.model_dump(mode="json"),
                enrichment_sha256=digest,
            )

    async def _compile(self, build: BuildRecord) -> None:
        config = await self._config(build.id)
        if build.manifest_storage_key and build.manifest_sha256:
            value = await self._artifacts.read_manifest(
                build,
                max_bytes=config.artifact_max_bytes,
            )
            MCPManifest.model_validate_json(value)
            return
        if build.canonical_snapshot_id is None:
            raise InvalidStateError("Build has no canonical snapshot")
        snapshot = await self._canonicalization.get_snapshot(build.canonical_snapshot_id)
        enrichment = await self._enrichment(build.id)
        canonical = self._analysis.apply(snapshot.canonical, enrichment)
        generation = await self._generation(build.id)
        async with self._database.session_scope() as session:
            project = await self._projects.get(session, build.project_id)
        if project is None:
            raise NotFoundError("Project was not found")
        resources = await self._artifacts.documentation_resources(
            generation,
            project_slug=project.slug,
            max_bytes=config.artifact_max_bytes,
        )
        await self._cancellation_checkpoint(build.id)
        manifest = compile_manifest(
            canonical,
            project_id=str(project.id),
            project_name=project.name,
            project_slug=project.slug,
            build_id=str(build.id),
            created_at=build.created_at,
            security_selections=map_credentials(
                canonical,
                config.credentials,
                excluded_operation_keys=frozenset(
                    item.operation_key for item in config.excluded_operations
                ),
            ),
            excluded_operation_keys=frozenset(
                item.operation_key for item in config.excluded_operations
            ),
            resources=resources,
            canonical_digest=snapshot.canonical_sha256,
            compiler_version=build.compiler_version,
            runtime_compatibility=build.runtime_compatibility,
            prompt_bundle_version=build.prompt_bundle_version,
            analysis_model=build.analysis_model,
            validation_model=build.validation_model,
            embedding_model=build.embedding_model,
            timeout_ms=config.runtime_timeout_ms,
            max_request_bytes=config.runtime_max_request_bytes,
            max_response_bytes=config.runtime_max_response_bytes,
        )
        observe_generated_operations(len(manifest.tools))
        stored = await self._artifacts.store_manifest(
            manifest,
            max_bytes=config.artifact_max_bytes,
        )
        try:
            async with self._database.session_scope() as session:
                await self._builds.set_manifest(
                    session,
                    build.id,
                    manifest_sha256=stored.sha256,
                    manifest_storage_key=stored.storage_key,
                )
        except InvalidStateError:
            await self._schedule_orphan_object(build, stored.storage_key, "manifest")
            raise

    async def _validate(self, build: BuildRecord) -> bool:
        config = await self._config(build.id)
        async with self._database.session_scope() as session:
            existing = await self._reports.get_report(session, build.id)
        if existing is not None:
            return existing.overall_status is ValidationStatus.PASS
        if build.canonical_snapshot_id is None:
            raise InvalidStateError("Build has no canonical snapshot")
        snapshot = await self._canonicalization.get_snapshot(build.canonical_snapshot_id)
        enrichment = await self._enrichment(build.id)
        canonical = self._analysis.apply(snapshot.canonical, enrichment)
        manifest_bytes = await self._artifacts.read_manifest(
            build,
            max_bytes=config.artifact_max_bytes,
        )
        manifest = MCPManifest.model_validate_json(manifest_bytes)
        report = await self._validation.validate(
            build=build,
            config=config,
            canonical=canonical,
            canonical_sha256=snapshot.canonical_sha256,
            manifest=manifest,
            manifest_bytes=manifest_bytes,
            cancellation_check=lambda: self._cancellation_checkpoint(build.id),
        )
        return report.overall_status is ValidationStatus.PASS

    async def _package(self, build: BuildRecord) -> None:
        config = await self._config(build.id)
        if build.artifact_storage_key and build.artifact_sha256:
            await self._artifacts.read_export(build, max_bytes=config.artifact_max_bytes)
            return
        manifest_bytes = await self._artifacts.read_manifest(
            build,
            max_bytes=config.artifact_max_bytes,
        )
        manifest = MCPManifest.model_validate_json(manifest_bytes)
        async with self._database.session_scope() as session:
            project = await self._projects.get(session, build.project_id)
            report = await self._reports.get_report(session, build.id)
        if project is None or report is None:
            raise InvalidStateError("Build packaging inputs are incomplete")
        stored = await self._artifacts.package(
            build=build,
            config=config,
            manifest=manifest,
            validation=report,
            project_name=project.name,
            project_slug=project.slug,
            source_version_ids=[str(value) for value in await self._source_version_ids(build.id)],
        )
        try:
            async with self._database.session_scope() as session:
                await self._builds.set_artifact(
                    session,
                    build.id,
                    artifact_sha256=stored.sha256,
                    artifact_storage_key=stored.storage_key,
                )
        except InvalidStateError:
            await self._schedule_orphan_object(build, stored.storage_key, "export")
            raise

    async def _ready(self, build_id: UUID) -> BuildRecord:
        async with self._database.session_scope() as session:
            build = await self._builds.mark_ready(session, build_id)
            await self._audit.append(
                session,
                actor_user_id=build.requested_by,
                event_type="build.ready",
                entity_type="build",
                entity_id=build.id,
                project_id=build.project_id,
                metadata={
                    "sequence": build.sequence,
                    "manifest_sha256": build.manifest_sha256,
                    "artifact_sha256": build.artifact_sha256,
                },
            )
            return build

    async def _get(self, build_id: UUID) -> BuildRecord:
        async with self._database.session_scope() as session:
            build = await self._builds.get(session, build_id)
            if build is None:
                raise NotFoundError("Build was not found")
            return build

    async def _cancellation_checkpoint(self, build_id: UUID) -> None:
        async with self._database.session_scope() as session:
            if await self._builds.cancellation_requested(session, build_id):
                raise BuildCancellationRequested

    async def _acknowledge_cancellation(self, build_id: UUID) -> BuildRecord:
        async with self._database.session_scope() as session:
            build = await self._builds.get(session, build_id)
            if build is None:
                raise NotFoundError("Build was not found")
            if build.status is BuildStatus.CANCELLED:
                return build
            cleanup_job = None
            if self._cleanup is not None:
                cleanup_job = await self._cleanup.create_job(
                    session,
                    kind=CleanupJobKind.ORPHAN_GUARD,
                    idempotency_key=f"build-cancellation:{build.id}",
                    project_id=build.project_id,
                    requested_by=build.cancellation_requested_by,
                    request_id=None,
                )
                await self._cleanup.capture_build_target(session, cleanup_job.id, build.id)
                await self._cleanup.finalize_empty_job(session, cleanup_job.id)
            cancelled = await self._builds.acknowledge_cancellation(session, build.id)
            await self._audit.append(
                session,
                actor_user_id=build.cancellation_requested_by,
                event_type="build.cancelled",
                entity_type="build",
                entity_id=build.id,
                project_id=build.project_id,
                metadata={
                    "acknowledgement": "worker",
                    "cleanup_job_id": str(cleanup_job.id) if cleanup_job else None,
                },
            )
            return cancelled

    async def _schedule_orphan_object(
        self,
        build: BuildRecord,
        storage_key: str,
        artifact_kind: str,
    ) -> None:
        if self._cleanup is None:
            await self._storage.delete(storage_key)
            return
        async with self._database.session_scope() as session:
            job = await self._cleanup.create_job(
                session,
                kind=CleanupJobKind.ORPHAN_GUARD,
                idempotency_key=(
                    f"build-orphan:{build.id}:{artifact_kind}:"
                    f"{hashlib.sha256(storage_key.encode()).hexdigest()}"
                ),
                project_id=build.project_id,
                requested_by=build.requested_by,
                request_id=None,
            )
            await self._cleanup.add_object_target(session, job.id, storage_key)

    async def _transition(
        self,
        build_id: UUID,
        expected: BuildStatus,
        target: BuildStatus,
    ) -> BuildRecord:
        async with self._database.session_scope() as session:
            return await self._builds.transition(
                session,
                build_id,
                expected=expected,
                target=target,
            )

    async def _source_version_ids(self, build_id: UUID) -> list[UUID]:
        async with self._database.session_scope() as session:
            values = await self._builds.source_version_ids(session, build_id)
        if not values:
            raise InvalidStateError("Build has no bound source versions")
        return values

    async def _config(self, build_id: UUID) -> BuildConfiguration:
        async with self._database.session_scope() as session:
            config = await self._builds.get_build_config(session, build_id)
        if config is None:
            raise NotFoundError("Build was not found")
        return config

    async def _generation(self, build_id: UUID) -> DocumentIndexGenerationRecord:
        async with self._database.session_scope() as session:
            generation = await self._generations.get_for_build(session, build_id)
        if generation is None:
            raise InvalidStateError("Build has no document index generation")
        return generation

    async def _reusable_enrichment(
        self,
        build: BuildRecord,
        canonical: CanonicalApi,
        generation: DocumentIndexGenerationRecord,
        config: BuildConfiguration,
    ) -> dict[str, OperationEnrichment]:
        if build.previous_build_id is None or build.trigger is not BuildTrigger.SOURCE_CHANGE:
            return {}
        async with self._database.session_scope() as session:
            previous = await self._builds.get(session, build.previous_build_id)
            previous_config = await self._builds.get_build_config(session, build.previous_build_id)
            previous_enrichment_raw = await self._builds.get_enrichment(
                session,
                build.previous_build_id,
            )
            previous_generation = await self._generations.get_for_build(
                session,
                build.previous_build_id,
            )
        if (
            previous is None
            or previous.canonical_snapshot_id is None
            or previous_config is None
            or previous_enrichment_raw is None
            or previous_generation is None
        ):
            return {}
        previous_snapshot = await self._canonicalization.get_snapshot(
            previous.canonical_snapshot_id
        )
        reusable = select_reusable_enrichment(
            current_build=build,
            previous_build=previous,
            current_canonical=canonical,
            previous_canonical=previous_snapshot.canonical,
            current_generation=generation,
            previous_generation=previous_generation,
            current_config=config,
            previous_config=previous_config,
            previous_enrichment=EnrichmentSnapshot.model_validate(previous_enrichment_raw),
            prompt_template_id=OPERATION_ENRICHMENT_PROMPT.id,
            prompt_template_version=OPERATION_ENRICHMENT_PROMPT.version,
        )
        return reusable

    async def _enrichment(self, build_id: UUID) -> EnrichmentSnapshot:
        async with self._database.session_scope() as session:
            raw = await self._builds.get_enrichment(session, build_id)
        if raw is None:
            raise InvalidStateError("Build has no semantic enrichment snapshot")
        return EnrichmentSnapshot.model_validate(raw)
