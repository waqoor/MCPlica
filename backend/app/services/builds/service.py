from collections.abc import Iterable
from typing import Protocol, cast
from uuid import UUID, uuid4

from mcp_contracts import RUNTIME_COMPATIBILITY, MCPManifest
from mcp_contracts.json_types import JsonObject
from pydantic import TypeAdapter

from app.clients.build_queue import BuildQueueClient
from app.clients.database import DatabaseClient
from app.compilers.mcp.compiler import COMPILER_VERSION
from app.core.config import Settings
from app.core.exceptions import (
    ClientError,
    ConflictError,
    InvalidStateError,
    NotFoundError,
    ValidationError,
)
from app.domain.analysis import EnrichmentSnapshot
from app.domain.builds import (
    TERMINAL_STATUSES,
    BuildAIRunRecord,
    BuildConfiguration,
    BuildCredentialSnapshot,
    BuildDiff,
    BuildExclusionSnapshot,
    BuildOperationPageItem,
    BuildOperationView,
    BuildRecord,
    BuildStatus,
    BuildTrigger,
)
from app.domain.sources import (
    SourceConfigurationDiscoveryRecord,
    SourceKind,
    source_configuration_fingerprint,
)
from app.domain.validation import OperationExclusionRecord, ValidationReportRecord
from app.repositories.audit import AuditRepository
from app.repositories.builds import BuildAIRunRepository, BuildRepository
from app.repositories.canonical import CanonicalRepository
from app.repositories.credentials import CredentialRepository
from app.repositories.projects import ProjectRepository
from app.repositories.sources import SourceRepository
from app.repositories.validation import ValidationRepository
from app.services.artifacts import ArtifactService
from app.services.build_admission import BuildAdmissionDispatcher
from app.services.builds.cancellation import BuildCancellationService
from app.services.builds.diff import diff_builds
from app.services.builds.operation_paging import (
    OperationPageCandidate,
    OperationScope,
    page_operation_candidates,
)
from app.services.builds.readiness import credential_mapping_readiness
from app.services.cleanup import CleanupService
from app.services.settings import SettingsService

PROMPT_BUNDLE_VERSION = "1.0.0"
_JSON_OBJECT: TypeAdapter[JsonObject] = TypeAdapter(JsonObject)


class SourceConfigurationProvider(Protocol):
    async def discover_configuration(
        self, project_id: UUID
    ) -> SourceConfigurationDiscoveryRecord: ...


class BuildService:
    def __init__(
        self,
        database: DatabaseClient,
        builds: BuildRepository,
        ai_runs: BuildAIRunRepository,
        snapshots: CanonicalRepository,
        sources: SourceRepository,
        source_configuration: SourceConfigurationProvider,
        projects: ProjectRepository,
        credentials: CredentialRepository,
        validation: ValidationRepository,
        audit: AuditRepository,
        settings: SettingsService,
        queue: BuildQueueClient,
        defaults: Settings,
        artifacts: ArtifactService,
        cleanup: CleanupService | None,
        admission: BuildAdmissionDispatcher,
    ) -> None:
        self._database = database
        self._builds = builds
        self._ai_runs = ai_runs
        self._snapshots = snapshots
        self._sources = sources
        self._source_configuration = source_configuration
        self._projects = projects
        self._credentials = credentials
        self._validation = validation
        self._audit = audit
        self._settings = settings
        self._queue = queue
        self._defaults = defaults
        self._artifacts = artifacts
        self._cleanup = cleanup
        self._cancellations = BuildCancellationService(
            builds,
            cleanup.repository if cleanup is not None else None,
            audit,
        )
        self._admission = admission

    async def create(
        self,
        *,
        project_id: UUID,
        requested_by: UUID,
        request_id: str | None,
        requested_trigger: BuildTrigger | None = None,
    ) -> BuildRecord:
        models = await self._settings.get_models()
        operational = await self._settings.get_operational()
        analysis_model = models.analysis_model
        validation_model = models.validation_model
        embedding_model = models.embedding_model
        missing = [
            name
            for name, value in (
                ("analysis_model", models.analysis_model),
                ("validation_model", models.validation_model),
                ("embedding_model", models.embedding_model),
            )
            if not value
        ]
        if missing:
            raise InvalidStateError("Build models are not configured: " + ", ".join(missing))
        assert analysis_model is not None
        assert validation_model is not None
        assert embedding_model is not None
        discovery = await self._source_configuration.discover_configuration(project_id)
        build_id = uuid4()
        async with self._database.session_scope() as session:
            project = await self._builds.lock_project(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
            if not project.is_enabled:
                raise InvalidStateError("Disabled Projects cannot start Builds")
            bindings = await self._sources.latest_bound_versions(session, project_id)
            current_configuration_sha256 = source_configuration_fingerprint(
                bindings=bindings,
                default_base_url=project.default_base_url,
                active_server_ref=project.active_server_ref,
                server_mappings=project.server_mappings,
            )
            if discovery.configuration_sha256 != current_configuration_sha256:
                raise ConflictError(
                    "Source or routing configuration changed during build preflight; retry"
                )
            if not discovery.routing_complete:
                raise InvalidStateError(
                    "Every operation must resolve to one applicable upstream server",
                    details={
                        "reason_code": "ROUTING_INCOMPLETE",
                        "remediation": "Resolve ambiguous server selections before building.",
                    },
                )
            primary = [
                item
                for item in bindings
                if item.source.is_primary
                and item.source.kind in {SourceKind.OPENAPI, SourceKind.API_INVENTORY}
            ]
            if len(primary) != 1:
                raise InvalidStateError(
                    "A Build requires exactly one versioned primary executable source"
                )
            previous = await self._builds.latest_ready(session, project_id)
            exclusions = await self._validation.list_exclusions(session, project_id)
            credentials = [
                credential
                for credential in await self._credentials.list(session, project_id)
                if credential.revoked_at is None
            ]
            credential_readiness = credential_mapping_readiness(
                discovery,
                credentials,
            )
            if not credential_readiness.complete:
                raise InvalidStateError(
                    "Upstream credential mapping is incomplete or ambiguous",
                    details={
                        "reason_code": "CREDENTIAL_MAPPING_INCOMPLETE",
                        "operation_keys": list(credential_readiness.unresolved_operation_keys),
                        "remediation": (
                            "Bind exactly one compatible active credential for every "
                            "required operation security alternative."
                        ),
                    },
                )
            build_config = BuildConfiguration(
                executable_configuration_sha256=current_configuration_sha256,
                excluded_operations=[
                    BuildExclusionSnapshot(
                        id=exclusion.id,
                        operation_key=exclusion.operation_key,
                        reason_code=exclusion.reason_code,
                        reason=exclusion.reason,
                    )
                    for exclusion in exclusions
                ],
                credentials=[
                    BuildCredentialSnapshot(
                        id=credential.id,
                        scheme_type=credential.scheme_type,
                        metadata=_JSON_OBJECT.validate_python(credential.metadata),
                    )
                    for credential in credentials
                ],
                default_base_url=project.default_base_url,
                active_server_ref=project.active_server_ref,
                server_mappings=project.server_mappings,
                include_documentation_in_analysis=(models.include_documentation_in_analysis),
                max_operations=operational.max_operations_per_project,
                max_context_chars=self._defaults.openrouter_max_context_chars,
                max_ai_concurrency=self._defaults.openrouter_max_concurrency,
                retrieval_top_k=self._defaults.semantic_retrieval_top_k,
                source_max_bytes=max(item.version.byte_size for item in bindings),
                document_max_bytes=max(
                    (
                        item.version.byte_size
                        for item in bindings
                        if item.source.kind is SourceKind.DOCUMENTATION
                    ),
                    default=1,
                ),
                document_max_text_chars=self._defaults.document_max_text_chars,
                pdf_max_pages=self._defaults.pdf_max_pages,
                documentation_chunk_chars=self._defaults.documentation_chunk_chars,
                documentation_chunk_overlap_chars=(
                    self._defaults.documentation_chunk_overlap_chars
                ),
                max_document_chunks=operational.max_document_chunks_per_project,
                max_document_parse_concurrency=(self._defaults.document_parse_max_concurrency),
                embedding_batch_size=self._defaults.embedding_batch_size,
                max_embedding_concurrency=self._defaults.openrouter_max_concurrency,
                runtime_timeout_ms=self._defaults.runtime_upstream_timeout_ms,
                runtime_max_request_bytes=self._defaults.runtime_max_request_bytes,
                runtime_max_response_bytes=self._defaults.runtime_max_response_bytes,
                runtime_manifest_max_bytes=self._defaults.runtime_manifest_max_bytes,
                artifact_max_bytes=self._defaults.build_artifact_max_bytes,
            )
            trigger: BuildTrigger
            if requested_trigger in {
                BuildTrigger.MANUAL_REVIEW,
                BuildTrigger.MANUAL_REBUILD,
            }:
                trigger = cast(BuildTrigger, requested_trigger)
            else:
                trigger = BuildTrigger.INITIAL if previous is None else BuildTrigger.SOURCE_CHANGE
            build = await self._builds.create(
                session,
                build_id=build_id,
                project_id=project_id,
                trigger=trigger,
                source_bindings=bindings,
                requested_by=requested_by,
                compiler_version=COMPILER_VERSION,
                runtime_compatibility=RUNTIME_COMPATIBILITY,
                analysis_model=analysis_model,
                validation_model=validation_model,
                embedding_model=embedding_model,
                prompt_bundle_version=PROMPT_BUNDLE_VERSION,
                build_config=build_config.model_dump(mode="json"),
            )
            await self._audit.append(
                session,
                actor_user_id=requested_by,
                event_type="build.created",
                entity_type="build",
                entity_id=build.id,
                project_id=project_id,
                request_id=request_id,
                metadata={
                    "sequence": build.sequence,
                    "trigger": build.trigger.value,
                    "source_version_ids": [str(item.version.id) for item in bindings],
                },
            )
        self._admission.wake()
        return build

    async def get(self, build_id: UUID) -> BuildRecord:
        async with self._database.session_scope() as session:
            build = await self._builds.get(session, build_id)
            if build is None:
                raise NotFoundError("Build was not found")
            return build

    async def list_for_project(
        self,
        project_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BuildRecord]:
        async with self._database.session_scope() as session:
            if await self._projects.get(session, project_id) is None:
                raise NotFoundError("Project was not found")
            return await self._builds.list_for_project(
                session,
                project_id,
                limit=limit,
                offset=offset,
            )

    async def page_for_project(
        self,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[BuildRecord], int, bool]:
        async with self._database.session_scope() as session:
            if await self._projects.get(session, project_id) is None:
                raise NotFoundError("Project was not found")
            return (
                await self._builds.list_for_project(
                    session,
                    project_id,
                    limit=limit,
                    offset=offset,
                ),
                await self._builds.count_all(session, project_id=project_id),
                await self._builds.active_for_project(session, project_id) is not None,
            )

    async def list_all(
        self,
        *,
        project_id: UUID | None = None,
        status: BuildStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BuildRecord]:
        async with self._database.session_scope() as session:
            return await self._builds.list_all(
                session,
                project_id=project_id,
                status=status,
                limit=limit,
                offset=offset,
            )

    async def page_all(
        self,
        *,
        project_id: UUID | None = None,
        status: BuildStatus | None = None,
        limit: int,
        offset: int,
    ) -> tuple[list[BuildRecord], int, bool]:
        async with self._database.session_scope() as session:
            counts = await self._builds.status_counts(session, project_id=project_id)
            return (
                await self._builds.list_all(
                    session,
                    project_id=project_id,
                    status=status,
                    limit=limit,
                    offset=offset,
                ),
                await self._builds.count_all(
                    session,
                    project_id=project_id,
                    status=status,
                ),
                any(
                    count > 0 and build_status not in TERMINAL_STATUSES
                    for build_status, count in counts.items()
                ),
            )

    async def metrics(self) -> tuple[int, int, int]:
        async with self._database.session_scope() as session:
            counts = await self._builds.status_counts(session)
        total = sum(counts.values())
        active = sum(count for status, count in counts.items() if status not in TERMINAL_STATUSES)
        return total, active, counts.get(BuildStatus.FAILED, 0)

    async def cancel(
        self,
        build_id: UUID,
        *,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> BuildRecord:
        async with self._database.session_scope() as session:
            existing = await self._builds.get(session, build_id)
            if existing is None:
                raise NotFoundError("Build was not found")
            build = await self._builds.request_cancellation(
                session,
                build_id,
                requested_by=actor_user_id,
            )
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="build.cancellation_requested",
                entity_type="build",
                entity_id=build_id,
                project_id=build.project_id,
                request_id=request_id,
                metadata={"previous_status": existing.status.value},
            )
        queue_acknowledged = False
        try:
            queue_acknowledged = await self._queue.cancel_queued_build(
                build_id,
                build.admission_token,
            )
        except ClientError:
            # The durable database request remains authoritative; a worker or later queue
            # recovery will observe it before performing more stage work.
            queue_acknowledged = False
        if not queue_acknowledged or build.admission_token is None:
            self._admission.wake()
            return build
        return await self._acknowledge_cancellation(
            build_id,
            admission_token=build.admission_token,
            actor_user_id=actor_user_id,
            request_id=request_id,
            acknowledgement="queue",
        )

    async def _acknowledge_cancellation(
        self,
        build_id: UUID,
        *,
        admission_token: UUID,
        actor_user_id: UUID | None,
        request_id: str | None,
        acknowledgement: str,
    ) -> BuildRecord:
        async with self._database.session_scope() as session:
            result = await self._cancellations.acknowledge(
                session,
                build_id=build_id,
                admission_token=admission_token,
                actor_user_id=actor_user_id,
                request_id=request_id,
                acknowledgement=acknowledgement,
            )
        if result.cleanup_job is not None:
            cleanup = self._cleanup
            assert cleanup is not None
            cleanup.notify()
        self._admission.wake()
        return result.build

    async def validation_report(self, build_id: UUID) -> ValidationReportRecord:
        async with self._database.session_scope() as session:
            if await self._builds.get(session, build_id) is None:
                raise NotFoundError("Build was not found")
            report = await self._validation.get_report(session, build_id)
            if report is None:
                raise InvalidStateError("Build validation report is not available yet")
            return report

    async def manifest(self, build_id: UUID) -> MCPManifest:
        build = await self.get(build_id)
        config = await self._config(build_id)
        value = await self._artifacts.read_manifest(
            build,
            max_bytes=config.artifact_max_bytes,
        )
        return MCPManifest.model_validate_json(value)

    async def manifest_bytes(self, build_id: UUID) -> bytes:
        build = await self.get(build_id)
        config = await self._config(build_id)
        return await self._artifacts.read_manifest(
            build,
            max_bytes=config.artifact_max_bytes,
        )

    async def export(self, build_id: UUID) -> tuple[BuildRecord, bytes]:
        build = await self.get(build_id)
        if build.status is not BuildStatus.READY:
            raise InvalidStateError("Only a READY Build can be exported")
        config = await self._config(build_id)
        value = await self._artifacts.read_export(
            build,
            max_bytes=config.artifact_max_bytes,
        )
        return build, value

    async def ai_runs(
        self, build_id: UUID, *, page: int, page_size: int
    ) -> tuple[list[BuildAIRunRecord], int]:
        async with self._database.session_scope() as session:
            if await self._builds.get(session, build_id) is None:
                raise NotFoundError("Build was not found")
            return await self._ai_runs.list_page_for_build(
                session,
                build_id,
                page=page,
                page_size=page_size,
            )

    async def diff(self, build_id: UUID) -> BuildDiff:
        async with self._database.session_scope() as session:
            build = await self._builds.get(session, build_id)
            if build is None:
                raise NotFoundError("Build was not found")
            if build.canonical_snapshot_id is None:
                raise InvalidStateError("Build canonical snapshot is not available yet")
            current = await self._snapshots.get(session, build.canonical_snapshot_id)
            if current is None:
                raise InvalidStateError("Build canonical snapshot is unavailable")
            current_raw = await self._builds.get_enrichment(session, build.id)
            previous = None
            previous_raw = None
            if build.previous_build_id is not None:
                previous_build = await self._builds.get(session, build.previous_build_id)
                if previous_build and previous_build.canonical_snapshot_id:
                    previous = await self._snapshots.get(
                        session,
                        previous_build.canonical_snapshot_id,
                    )
                    previous_raw = await self._builds.get_enrichment(
                        session,
                        previous_build.id,
                    )
        return diff_builds(
            current.canonical,
            previous.canonical if previous else None,
            current_enrichment=(
                EnrichmentSnapshot.model_validate(current_raw) if current_raw else None
            ),
            previous_enrichment=(
                EnrichmentSnapshot.model_validate(previous_raw) if previous_raw else None
            ),
        )

    async def operations(self, build_id: UUID) -> list[BuildOperationView]:
        items, total, _ = await self.operations_page(
            build_id,
            search=None,
            method=None,
            scope="all",
            limit=100_000,
            offset=0,
        )
        if len(items) != total:
            raise InvalidStateError("Build exceeds the supported operation ceiling")
        return [item.operation for item in items]

    async def operations_page(
        self,
        build_id: UUID,
        *,
        search: str | None,
        method: str | None,
        scope: OperationScope,
        limit: int,
        offset: int,
    ) -> tuple[list[BuildOperationPageItem], int, int]:
        if not 1 <= limit <= 100_000 or offset < 0:
            raise ValidationError("Operation page bounds are invalid")
        async with self._database.session_scope() as session:
            build = await self._builds.get(session, build_id)
            if build is None:
                raise NotFoundError("Build was not found")
            if build.canonical_snapshot_id is None:
                raise InvalidStateError("Build canonical snapshot is not available yet")
            snapshot = await self._snapshots.get(session, build.canonical_snapshot_id)
            config = await self._builds.get_build_config(session, build.id)
            enrichment_raw = await self._builds.get_enrichment(session, build.id)
            current_exclusions = await self._validation.list_exclusions(session, build.project_id)
        if snapshot is None or config is None:
            raise InvalidStateError("Build operation inputs are unavailable")
        manifest = await self.manifest(build_id) if build.manifest_storage_key is not None else None
        tools = {tool.operation_key: tool for tool in manifest.tools} if manifest else {}
        profiles = {profile.id: profile for profile in manifest.auth_profiles} if manifest else {}
        enrichment = EnrichmentSnapshot.model_validate(enrichment_raw) if enrichment_raw else None
        build_exclusions = {item.operation_key: item for item in config.excluded_operations}
        current_by_operation = {item.operation_key: item for item in current_exclusions}
        operations = sorted(snapshot.canonical.operations, key=lambda item: item.key)

        def candidates() -> Iterable[OperationPageCandidate]:
            for index, operation in enumerate(operations):
                tool = tools.get(operation.key)
                semantic = enrichment.operations.get(operation.key) if enrichment else None
                yield OperationPageCandidate(
                    index=index,
                    method=operation.method.value,
                    search_text=" ".join(
                        value
                        for value in [
                            operation.key,
                            operation.source_operation_id or "",
                            operation.method.value,
                            operation.path_template,
                            tool.name if tool else "",
                            semantic.title if semantic and semantic.title else "",
                            operation.summary or "",
                            *(semantic.warnings if semantic else []),
                        ]
                        if value
                    ),
                    excluded_in_build=operation.key in build_exclusions,
                    currently_excluded=operation.key in current_by_operation,
                )

        selected, total, policy_change_count = page_operation_candidates(
            candidates(),
            search=search,
            method=method,
            scope=scope,
            offset=offset,
            limit=limit,
        )
        result: list[BuildOperationPageItem] = []
        for candidate in selected:
            operation = operations[candidate.index]
            tool = tools.get(operation.key)
            semantic = enrichment.operations.get(operation.key) if enrichment else None
            exclusion = build_exclusions.get(operation.key)
            current_exclusion = current_by_operation.get(operation.key)
            auth_mapping: list[str] = []
            if tool and tool.security_profile_ref:
                profile = profiles.get(tool.security_profile_ref)
                if profile is not None:
                    auth_mapping.append(f"{profile.type}:{profile.credential_ref or 'unresolved'}")
            refs = [
                operation.provenance.operation,
                *operation.provenance.executable_fields.values(),
            ]
            seen_refs: set[tuple[UUID, str]] = set()
            provenance: list[JsonObject] = []
            for ref in refs:
                identity = (ref.source_version_id, ref.pointer)
                if identity in seen_refs:
                    continue
                seen_refs.add(identity)
                provenance.append(
                    {
                        "source_version_id": str(ref.source_version_id),
                        "path": ref.pointer,
                        "kind": "source",
                    }
                )
            result.append(
                BuildOperationPageItem(
                    operation=BuildOperationView(
                        key=operation.key,
                        source_operation_id=operation.source_operation_id,
                        method=operation.method.value,
                        path_template=operation.path_template,
                        tool_name=tool.name if tool else None,
                        title=(
                            semantic.title if semantic and semantic.title else operation.summary
                        ),
                        source_summary=operation.summary,
                        source_description=operation.description,
                        enriched_description=semantic.description if semantic else None,
                        input_schema=tool.input_schema if tool else None,
                        auth_mapping=auth_mapping,
                        provenance=provenance,
                        semantic_warnings=semantic.warnings if semantic else [],
                        confidence=semantic.confidence if semantic else None,
                        excluded_in_build=exclusion is not None,
                        build_exclusion_id=exclusion.id if exclusion else None,
                        build_exclusion_reason=exclusion.reason if exclusion else None,
                    ),
                    current_exclusion_id=(current_exclusion.id if current_exclusion else None),
                    current_exclusion_reason=(
                        current_exclusion.reason if current_exclusion else None
                    ),
                )
            )
        return result, total, policy_change_count

    async def list_exclusions(
        self,
        *,
        project_id: UUID,
    ) -> list[OperationExclusionRecord]:
        async with self._database.session_scope() as session:
            if await self._projects.get(session, project_id) is None:
                raise NotFoundError("Project was not found")
            return await self._validation.list_exclusions(session, project_id)

    async def create_exclusion(
        self,
        *,
        project_id: UUID,
        operation_key: str,
        reason: str,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> OperationExclusionRecord:
        normalized_operation_key = operation_key.strip()
        normalized_reason = reason.strip()
        if not normalized_operation_key or len(normalized_operation_key) > 160:
            raise ValidationError("Operation exclusion key is invalid")
        if not 5 <= len(normalized_reason) <= 2_000:
            raise ValidationError("Operation exclusion reason must contain 5 to 2000 characters")
        async with self._database.session_scope() as session:
            if await self._projects.lock(session, project_id) is None:
                raise NotFoundError("Project was not found")
            build = await self._builds.latest_with_canonical_snapshot(session, project_id)
            if build is None or build.canonical_snapshot_id is None:
                raise InvalidStateError("Project has no canonical operation snapshot")
            snapshot = await self._snapshots.get(session, build.canonical_snapshot_id)
            if snapshot is None:
                raise InvalidStateError("Project canonical operation snapshot is unavailable")
            if normalized_operation_key not in {item.key for item in snapshot.canonical.operations}:
                raise NotFoundError("Operation was not found in the latest Build snapshot")
            existing = await self._validation.list_exclusions(session, project_id)
            if any(item.operation_key == normalized_operation_key for item in existing):
                raise ConflictError("Operation already has a persistent exclusion")
            exclusion = await self._validation.create_exclusion(
                session,
                project_id=project_id,
                build_id=build.id,
                operation_key=normalized_operation_key,
                reason_code="user_requested",
                reason=normalized_reason,
                is_user_requested=True,
                created_by=actor_user_id,
            )
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="operation_exclusion.created",
                entity_type="operation_exclusion",
                entity_id=exclusion.id,
                project_id=project_id,
                request_id=request_id,
                metadata={
                    "operation_key": normalized_operation_key,
                    "origin_build_id": str(build.id),
                },
            )
            return exclusion

    async def delete_exclusion(
        self,
        *,
        project_id: UUID,
        exclusion_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> None:
        async with self._database.session_scope() as session:
            if await self._projects.lock(session, project_id) is None:
                raise NotFoundError("Project was not found")
            exclusion = await self._validation.get_exclusion(session, exclusion_id)
            if exclusion is None or exclusion.project_id != project_id:
                raise NotFoundError("Operation exclusion was not found")
            if not await self._validation.delete_exclusion(
                session,
                project_id=project_id,
                exclusion_id=exclusion_id,
            ):
                raise NotFoundError("Operation exclusion was not found")
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="operation_exclusion.deleted",
                entity_type="operation_exclusion",
                entity_id=exclusion_id,
                project_id=project_id,
                request_id=request_id,
                metadata={"operation_key": exclusion.operation_key},
            )

    async def _config(self, build_id: UUID) -> BuildConfiguration:
        async with self._database.session_scope() as session:
            config = await self._builds.get_build_config(session, build_id)
        if config is None:
            raise NotFoundError("Build was not found")
        return config
