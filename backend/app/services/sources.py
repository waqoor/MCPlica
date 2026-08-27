from __future__ import annotations

import asyncio
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePath
from typing import Literal, Protocol
from urllib.parse import urlsplit
from uuid import UUID

from mcp_contracts import CanonicalApi, CanonicalServer
from mcp_contracts.json_types import JsonObject
from pydantic import TypeAdapter

from app.clients.database import DatabaseClient
from app.clients.http import HttpClient
from app.clients.storage import AsyncReadable, BytesReader
from app.core.exceptions import ConflictError, InvalidStateError, NotFoundError, SourceParseError
from app.core.network_policy import UrlPolicy
from app.domain.builds import BuildConfiguration, BuildRecord
from app.domain.canonicalization import CanonicalSnapshotRecord
from app.domain.cleanup import CleanupJobRecord
from app.domain.indexing import DocumentIndexGenerationRecord, IndexGenerationStatus
from app.domain.projects import ProjectRoutingConfiguration
from app.domain.sources import (
    OperationSecurityRequirementRecord,
    OperationServerRoutingRecord,
    ProjectSourceRecord,
    SecuritySchemeDiscoveryRecord,
    ServerCandidateRecord,
    SourceConfigurationDiscoveryRecord,
    SourceIssueRecord,
    SourceKind,
    SourceOrigin,
    SourceSummaryRecord,
    SourceVersionMetadataRecord,
    SourceVersionRecord,
    source_configuration_fingerprint,
)
from app.parsers.documentation import DocumentChunk, detect_office_document_format
from app.parsers.structured import parse_json_or_yaml
from app.providers.storage import ArtifactStorage
from app.repositories.audit import AuditRepository
from app.repositories.builds import BuildRepository
from app.repositories.canonical import CanonicalRepository
from app.repositories.cleanup import lock_object_reference
from app.repositories.indexing import IndexGenerationRepository
from app.repositories.projects import ProjectRepository
from app.repositories.sources import SourceRepository
from app.services.cleanup import CleanupService
from app.services.settings import OperationalSettingsProvider

_DOCUMENT_CHUNKS = TypeAdapter(list[DocumentChunk])
_PREVIEW_CHAR_LIMIT = 20_000
_SUMMARY_MANIFEST_READ_CONCURRENCY = 4
_DOCUMENT_FORMAT_BY_EXTENSION = {
    ".csv": "csv",
    ".docx": "docx",
    ".htm": "html",
    ".html": "html",
    ".json": "json",
    ".markdown": "markdown",
    ".md": "markdown",
    ".pdf": "pdf",
    ".txt": "text",
    ".xlsx": "xlsx",
}
_DOCUMENT_FORMAT_BY_MEDIA_TYPE = {
    "application/json": "json",
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/xhtml+xml": "html",
    "text/csv": "csv",
    "text/html": "html",
    "text/markdown": "markdown",
    "text/plain": "text",
    "text/x-markdown": "markdown",
}


def _server_scope(
    pointer: str,
    source_format: str,
) -> Literal["root", "path", "operation", "project_default", "inventory"]:
    if "x-mcplica-project-default-base-url" in pointer:
        return "project_default"
    if source_format == "api-inventory/v1":
        return "inventory"
    parts = pointer.split("/")
    if "paths" not in parts:
        return "root"
    paths_index = parts.index("paths")
    servers_index = parts.index("servers") if "servers" in parts else len(parts)
    return "operation" if servers_index - paths_index >= 3 else "path"


def _inherited_active_server_ref(
    candidate_refs: list[str],
    servers: list[CanonicalServer],
    *,
    source_format: str,
    active_server_ref: str | None,
) -> str | None:
    """Apply the project-wide selection only where the parser inherits it."""

    if (
        active_server_ref is None
        or active_server_ref not in candidate_refs
        or len(candidate_refs) <= 1
    ):
        return None
    scopes_by_ref = {
        server.key: _server_scope(server.source_ref.pointer, source_format) for server in servers
    }
    candidate_scopes = {scopes_by_ref.get(ref) for ref in candidate_refs}
    inherited_scope = "inventory" if source_format == "api-inventory/v1" else "root"
    return active_server_ref if candidate_scopes == {inherited_scope} else None


@dataclass(frozen=True, slots=True)
class SourceVersionResult:
    version: SourceVersionRecord
    deduplicated: bool


@dataclass(frozen=True, slots=True)
class SourceCreationResult:
    source: ProjectSourceRecord
    version: SourceVersionRecord
    deduplicated: bool


class SourceCanonicalizer(Protocol):
    async def current_source_versions(self, project_id: UUID) -> list[UUID]: ...

    async def canonicalize(
        self,
        project_id: UUID,
        source_version_ids: list[UUID],
        *,
        max_source_bytes: int,
        routing: ProjectRoutingConfiguration | None = None,
    ) -> CanonicalApi: ...


def _parse_executable(value: bytes) -> tuple[str, JsonObject]:
    if value.startswith(b"PK\x03\x04"):
        raise SourceParseError("Archive uploads are not accepted as executable sources")
    detected, parsed = parse_json_or_yaml(value)
    return detected, parsed


def _detect_format(
    kind: SourceKind,
    source_name: str,
    value: bytes,
    media_type: str,
    *,
    filename: str | None = None,
) -> str:
    if not value:
        raise SourceParseError("Source content is empty")
    if kind in {SourceKind.OPENAPI, SourceKind.API_INVENTORY}:
        detected, parsed = _parse_executable(value)
        if kind is SourceKind.OPENAPI:
            version = str(parsed.get("openapi", ""))
            if not (version.startswith("3.0.") or version.startswith("3.1.")):
                raise SourceParseError("OpenAPI source must declare supported 3.0.x or 3.1.x")
        elif parsed.get("schema") != "api-inventory/v1":
            raise SourceParseError("API Inventory source must declare schema api-inventory/v1")
        return detected

    normalized_media = media_type.partition(";")[0].strip().casefold()
    name = (filename or source_name).strip().casefold()
    extension_format = _DOCUMENT_FORMAT_BY_EXTENSION.get(PurePath(name).suffix)
    media_format = _DOCUMENT_FORMAT_BY_MEDIA_TYPE.get(normalized_media)
    if value.startswith(b"%PDF-") or media_format == "pdf" or extension_format == "pdf":
        if not value.startswith(b"%PDF-"):
            raise SourceParseError("PDF documentation does not contain a valid PDF header")
        return "pdf"
    if value.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return detect_office_document_format(value)
    if media_format in {"xlsx", "docx"} or extension_format in {"xlsx", "docx"}:
        raise SourceParseError("Office document does not contain a valid XLSX or DOCX package")
    try:
        value.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceParseError(
            "Documentation must be UTF-8 JSON, Markdown, text, CSV, or HTML, "
            "or a valid XLSX, DOCX, or PDF"
        ) from exc
    if extension_format is not None:
        return extension_format
    if media_format is not None:
        return media_format
    if normalized_media.startswith("text/"):
        return "text"
    raise SourceParseError(
        "Unsupported documentation format; use JSON, Markdown, TXT, CSV, XLSX, DOCX, or PDF"
    )


class SourceService:
    def __init__(
        self,
        database: DatabaseClient,
        sources: SourceRepository,
        projects: ProjectRepository,
        builds: BuildRepository,
        snapshots: CanonicalRepository,
        generations: IndexGenerationRepository,
        audit: AuditRepository,
        storage: ArtifactStorage,
        http: HttpClient,
        url_policy: UrlPolicy,
        settings: OperationalSettingsProvider,
        *,
        canonicalization: SourceCanonicalizer | None = None,
        document_max_bytes: int,
        fetch_max_bytes: int,
        fetch_max_redirects: int,
        fetch_max_attempts: int,
        cleanup: CleanupService | None = None,
    ) -> None:
        self._database = database
        self._sources = sources
        self._projects = projects
        self._builds = builds
        self._snapshots = snapshots
        self._generations = generations
        self._audit = audit
        self._storage = storage
        self._http = http
        self._url_policy = url_policy
        self._settings = settings
        self._canonicalization = canonicalization
        self._document_max_bytes = document_max_bytes
        self._fetch_max_bytes = fetch_max_bytes
        self._fetch_max_redirects = fetch_max_redirects
        self._fetch_max_attempts = fetch_max_attempts
        self._cleanup = cleanup

    async def list(self, project_id: UUID) -> list[ProjectSourceRecord]:
        async with self._database.session_scope() as session:
            if await self._projects.get(session, project_id) is None:
                raise NotFoundError("Project was not found")
            return await self._sources.list_sources(session, project_id)

    async def list_summaries(
        self,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SourceSummaryRecord], int]:
        async with self._database.session_scope() as session:
            if await self._projects.get(session, project_id) is None:
                raise NotFoundError("Project was not found")
            items, total = await self._sources.list_source_summaries(
                session,
                project_id,
                limit=limit,
                offset=offset,
            )
            build_ids = sorted(
                {item.metadata_build_id for item in items if item.metadata_build_id is not None},
                key=str,
            )
            build_contexts = await self._builds.get_many_with_configs(session, build_ids)
            snapshot_ids = sorted(
                {
                    build.canonical_snapshot_id
                    for build, _config in build_contexts.values()
                    if build.canonical_snapshot_id is not None
                },
                key=str,
            )
            snapshots = await self._snapshots.get_many(session, snapshot_ids)
            generations = await self._generations.get_for_builds(session, build_ids)
        return (
            await self._enrich_summary_metadata(
                items,
                build_contexts=build_contexts,
                snapshots=snapshots,
                generations=generations,
            ),
            total,
        )

    async def _enrich_summary_metadata(
        self,
        items: list[SourceSummaryRecord],
        *,
        build_contexts: dict[UUID, tuple[BuildRecord, BuildConfiguration]],
        snapshots: dict[UUID, CanonicalSnapshotRecord],
        generations: dict[UUID, DocumentIndexGenerationRecord],
    ) -> list[SourceSummaryRecord]:
        operation_counts: dict[UUID, Counter[UUID]] = {}
        valid_items = [
            item
            for item in items
            if item.health == "valid"
            and item.latest_version is not None
            and item.metadata_build_id is not None
        ]
        for item in valid_items:
            if item.source.kind is SourceKind.DOCUMENTATION:
                continue
            build_id = item.metadata_build_id
            assert build_id is not None
            build_context = build_contexts.get(build_id)
            if build_context is None:
                raise InvalidStateError("Source summary build metadata is unavailable")
            build, _config = build_context
            if build.canonical_snapshot_id is None:
                raise InvalidStateError("Ready source summary build has no canonical snapshot")
            if build.canonical_snapshot_id not in operation_counts:
                snapshot = snapshots.get(build.canonical_snapshot_id)
                if snapshot is None:
                    raise InvalidStateError("Source summary canonical snapshot is unavailable")
                operation_counts[build.canonical_snapshot_id] = Counter(
                    operation.provenance.operation.source_version_id
                    for operation in snapshot.canonical.operations
                )

        ready_document_generations: dict[UUID, DocumentIndexGenerationRecord] = {}
        for item in valid_items:
            if item.source.kind is not SourceKind.DOCUMENTATION:
                continue
            build_id = item.metadata_build_id
            assert build_id is not None
            generation = generations.get(build_id)
            if generation is None:
                raise InvalidStateError("Ready source summary build has no index generation")
            if generation.status is not IndexGenerationStatus.READY:
                raise InvalidStateError("Ready source summary index generation is incomplete")
            ready_document_generations[generation.id] = generation

        semaphore = asyncio.Semaphore(_SUMMARY_MANIFEST_READ_CONCURRENCY)

        async def load_chunk_counts(
            generation: DocumentIndexGenerationRecord,
        ) -> tuple[UUID, Counter[UUID]]:
            build_context = build_contexts.get(generation.build_id)
            if build_context is None:
                raise InvalidStateError("Index generation build metadata is unavailable")
            async with semaphore:
                chunks = await self._read_document_chunks(
                    generation,
                    max_bytes=build_context[1].artifact_max_bytes,
                )
            return generation.id, Counter(chunk.source_version_id for chunk in chunks)

        chunk_counts = dict(
            await asyncio.gather(
                *(
                    load_chunk_counts(generation)
                    for generation in sorted(
                        ready_document_generations.values(),
                        key=lambda value: str(value.id),
                    )
                )
            )
        )

        enriched: list[SourceSummaryRecord] = []
        for item in items:
            update: dict[str, object] = {}
            build_id = item.metadata_build_id
            version = item.latest_version
            if build_id is not None and version is not None:
                generation = generations.get(build_id)
                if generation is not None:
                    update["index_generation_id"] = generation.id
                if item.health == "valid":
                    if item.source.kind is SourceKind.DOCUMENTATION:
                        assert generation is not None
                        update["indexed_chunk_count"] = chunk_counts[generation.id][version.id]
                    else:
                        build_context = build_contexts.get(build_id)
                        assert build_context is not None
                        snapshot_id = build_context[0].canonical_snapshot_id
                        assert snapshot_id is not None
                        update["operation_count"] = operation_counts[snapshot_id][version.id]
            enriched.append(item.model_copy(update=update))
        return enriched

    async def _read_document_chunks(
        self,
        generation: DocumentIndexGenerationRecord,
        *,
        max_bytes: int,
    ) -> list[DocumentChunk]:
        if (
            generation.chunk_manifest_storage_key is None
            or generation.chunk_manifest_sha256 is None
        ):
            raise InvalidStateError("Ready index generation has no complete chunk manifest")
        manifest = await self._storage.get(
            generation.chunk_manifest_storage_key,
            max_bytes=max_bytes,
        )
        if hashlib.sha256(manifest).hexdigest() != generation.chunk_manifest_sha256:
            raise InvalidStateError("Documentation chunk manifest hash verification failed")
        try:
            chunks = _DOCUMENT_CHUNKS.validate_json(manifest)
        except ValueError as exc:
            raise InvalidStateError("Documentation chunk manifest is malformed") from exc
        if any(
            chunk.project_id != generation.project_id or chunk.generation_id != generation.id
            for chunk in chunks
        ):
            raise InvalidStateError("Documentation chunk manifest provenance is inconsistent")
        return chunks

    async def discover_configuration(self, project_id: UUID) -> SourceConfigurationDiscoveryRecord:
        if self._canonicalization is None:
            raise InvalidStateError("Source configuration discovery is unavailable")
        async with self._database.session_scope() as session:
            project = await self._projects.get(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
        source_version_ids = await self._canonicalization.current_source_versions(project_id)
        if not source_version_ids:
            raise InvalidStateError("Project has no source versions to inspect")
        canonical = await self._canonicalization.canonicalize(
            project_id,
            source_version_ids,
            max_source_bytes=max(self._document_max_bytes, self._fetch_max_bytes),
            routing=ProjectRoutingConfiguration(default_base_url=project.default_base_url),
        )
        applicable: dict[str, list[str]] = {server.key: [] for server in canonical.servers}
        operation_rows: list[OperationServerRoutingRecord] = []
        for operation in canonical.operations:
            for candidate in operation.server_candidates:
                applicable[candidate].append(operation.key)
            configured = project.server_mappings.get(operation.key)
            if configured is None:
                configured = _inherited_active_server_ref(
                    operation.server_candidates,
                    canonical.servers,
                    source_format=canonical.source_format,
                    active_server_ref=project.active_server_ref,
                )
            selection_error = None
            if configured is not None and configured not in operation.server_candidates:
                selection_error = "Configured server is not applicable to this operation"
                selected = None
            else:
                selected = configured or operation.server_ref
            operation_rows.append(
                OperationServerRoutingRecord(
                    operation_key=operation.key,
                    method=operation.method.value,
                    path=operation.path_template,
                    candidate_refs=operation.server_candidates,
                    selected_server_ref=selected,
                    configured_server_ref=configured,
                    selection_required=selected is None,
                    selection_error=selection_error,
                )
            )

        server_rows = [
            ServerCandidateRecord(
                ref=server.key,
                url=str(server.url),
                description=server.description,
                scope=_server_scope(server.source_ref.pointer, canonical.source_format),
                source_pointer=server.source_ref.pointer,
                applicable_operation_keys=sorted(applicable[server.key]),
            )
            for server in canonical.servers
        ]
        security_rows: list[SecuritySchemeDiscoveryRecord] = []
        for name, scheme in sorted(canonical.security_schemes.items()):
            operations = [
                operation
                for operation in canonical.operations
                if any(name in requirement.scheme_scopes for requirement in operation.security)
            ]
            security_rows.append(
                SecuritySchemeDiscoveryRecord(
                    name=name,
                    type=scheme.type.value,
                    location=scheme.location,
                    parameter_name=scheme.name,
                    token_url=str(scheme.token_url) if scheme.token_url is not None else None,
                    advertised_scopes=scheme.scopes,
                    applicable_operation_keys=sorted(operation.key for operation in operations),
                    optional_for_all_operations=bool(operations)
                    and all(
                        any(not requirement.scheme_scopes for requirement in operation.security)
                        for operation in operations
                    ),
                    source_pointer=scheme.source_ref.pointer,
                )
            )
        security_requirements = [
            OperationSecurityRequirementRecord(
                operation_key=operation.key,
                alternatives=[
                    {
                        name: list(scopes)
                        for name, scopes in sorted(requirement.scheme_scopes.items())
                    }
                    for requirement in operation.security
                ],
                anonymous_allowed=any(
                    not requirement.scheme_scopes for requirement in operation.security
                ),
            )
            for operation in canonical.operations
            if operation.security
        ]
        routing_complete = all(
            row.selected_server_ref is not None and row.selection_error is None
            for row in operation_rows
        )
        return SourceConfigurationDiscoveryRecord(
            source_version_ids=source_version_ids,
            configuration_sha256=source_configuration_fingerprint(
                source_version_ids=source_version_ids,
                default_base_url=project.default_base_url,
                active_server_ref=project.active_server_ref,
                server_mappings=project.server_mappings,
            ),
            servers=server_rows,
            operations=operation_rows,
            security_schemes=security_rows,
            security_requirements=security_requirements,
            routing_complete=routing_complete,
        )

    async def create(
        self,
        *,
        project_id: UUID,
        kind: SourceKind,
        name: str,
        origin_type: SourceOrigin,
        source_url: str | None,
        is_primary: bool,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> ProjectSourceRecord:
        normalized_name, normalized_url = self._normalize_source_definition(
            kind=kind,
            name=name,
            origin_type=origin_type,
            source_url=source_url,
            is_primary=is_primary,
        )
        if is_primary:
            raise InvalidStateError(
                "Primary designation requires an atomic source-with-first-version request"
            )
        async with self._database.session_scope() as session:
            if await self._projects.lock(session, project_id) is None:
                raise NotFoundError("Project was not found")
            source = await self._sources.create_source(
                session,
                project_id=project_id,
                kind=kind,
                name=normalized_name,
                origin_type=origin_type,
                source_url=normalized_url,
                is_primary=False,
            )
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="source.created",
                entity_type="project_source",
                entity_id=source.id,
                project_id=project_id,
                request_id=request_id,
                metadata={"kind": kind.value, "origin_type": origin_type.value},
            )
            return source

    async def create_with_upload(
        self,
        *,
        source_id: UUID,
        project_id: UUID,
        kind: SourceKind,
        name: str,
        is_primary: bool,
        content: AsyncReadable,
        media_type: str,
        filename: str | None,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> SourceCreationResult:
        normalized_name, _ = self._normalize_source_definition(
            kind=kind,
            name=name,
            origin_type=SourceOrigin.UPLOAD,
            source_url=None,
            is_primary=is_primary,
        )
        existing = await self._existing_creation(
            source_id=source_id,
            project_id=project_id,
            kind=kind,
            name=normalized_name,
            origin_type=SourceOrigin.UPLOAD,
            source_url=None,
        )
        if existing is not None:
            return existing
        operational = await self._settings.get_operational()
        max_bytes = (
            min(self._document_max_bytes, operational.max_upload_bytes)
            if kind is SourceKind.DOCUMENTATION
            else operational.max_upload_bytes
        )
        staged = await self._storage.stage_stream(
            f"projects/{project_id}/sources",
            content,
            max_bytes=max_bytes,
        )
        guard_id: UUID | None = None
        try:
            value = await self._storage.get_staged(staged, max_bytes=max_bytes)
            detected_format = _detect_format(
                kind,
                normalized_name,
                value,
                media_type,
                filename=filename,
            )
            guard_id = await self._arm_staged_guard(
                staged,
                project_id=project_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
            stored = await self._storage.commit_staged(staged)
        except BaseException:
            await self._storage.discard_staged(staged)
            if guard_id is not None:
                await self._release_guard(guard_id)
            raise
        try:
            result = await self._persist_created_source(
                source_id=source_id,
                project_id=project_id,
                kind=kind,
                name=normalized_name,
                origin_type=SourceOrigin.UPLOAD,
                source_url=None,
                is_primary=is_primary,
                content_sha256=stored.content_sha256,
                media_type=media_type,
                storage_key=stored.storage_key,
                byte_size=stored.byte_size,
                detected_format=detected_format,
                source_etag=None,
                source_last_modified=None,
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
        except BaseException:
            await self._release_guard(guard_id)
            raise
        await self._resolve_guard(guard_id)
        return result

    async def create_with_url(
        self,
        *,
        source_id: UUID,
        project_id: UUID,
        kind: SourceKind,
        name: str,
        source_url: str,
        is_primary: bool,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> SourceCreationResult:
        normalized_name, normalized_url = self._normalize_source_definition(
            kind=kind,
            name=name,
            origin_type=SourceOrigin.URL,
            source_url=source_url,
            is_primary=is_primary,
        )
        assert normalized_url is not None
        existing = await self._existing_creation(
            source_id=source_id,
            project_id=project_id,
            kind=kind,
            name=normalized_name,
            origin_type=SourceOrigin.URL,
            source_url=normalized_url,
        )
        if existing is not None:
            return existing
        response = await self._http.fetch_bounded(
            normalized_url,
            policy=self._url_policy,
            max_bytes=self._fetch_max_bytes,
            max_redirects=self._fetch_max_redirects,
            headers={
                "Accept": (
                    "application/json, application/yaml, text/*, application/pdf, "
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, "
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            },
            max_attempts=self._fetch_max_attempts,
        )
        media_type = response.headers.get("Content-Type", "application/octet-stream")
        remote_name = PurePath(urlsplit(normalized_url).path).name or normalized_name
        detected_format = _detect_format(
            kind,
            normalized_name,
            response.body,
            media_type,
            filename=remote_name,
        )
        staged = await self._storage.stage_stream(
            f"projects/{project_id}/sources",
            BytesReader(response.body),
            max_bytes=self._fetch_max_bytes,
        )
        guard_id: UUID | None = None
        try:
            guard_id = await self._arm_staged_guard(
                staged,
                project_id=project_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
            stored = await self._storage.commit_staged(staged)
            result = await self._persist_created_source(
                source_id=source_id,
                project_id=project_id,
                kind=kind,
                name=normalized_name,
                origin_type=SourceOrigin.URL,
                source_url=normalized_url,
                is_primary=is_primary,
                content_sha256=stored.content_sha256,
                media_type=media_type,
                storage_key=stored.storage_key,
                byte_size=stored.byte_size,
                detected_format=detected_format,
                source_etag=response.headers.get("ETag"),
                source_last_modified=response.headers.get("Last-Modified"),
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
        except BaseException:
            await self._storage.discard_staged(staged)
            await self._release_guard(guard_id)
            raise
        await self._resolve_guard(guard_id)
        return result

    async def update(
        self,
        *,
        project_id: UUID,
        source_id: UUID,
        name: str | None,
        is_primary: bool | None,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> ProjectSourceRecord:
        async with self._database.session_scope() as session:
            if await self._projects.lock(session, project_id) is None:
                raise NotFoundError("Project was not found")
            source = await self._sources.lock_source(session, source_id)
            if source is None or source.project_id != project_id:
                raise NotFoundError("Source was not found")
            updated = source
            if name is not None:
                normalized_name = name.strip()
                if not normalized_name:
                    raise SourceParseError("Source name cannot be empty")
                renamed = await self._sources.update_name(session, source_id, normalized_name)
                assert renamed is not None
                updated = renamed
            if is_primary is False and updated.is_primary:
                raise InvalidStateError(
                    "Promote another executable source instead of clearing the primary"
                )
            if is_primary is True:
                promoted = await self._sources.promote_executable(
                    session,
                    project_id=project_id,
                    source_id=source_id,
                )
                if promoted is None:
                    raise InvalidStateError(
                        "Only a versioned executable source can be promoted to primary"
                    )
                updated = promoted
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="source.updated",
                entity_type="project_source",
                entity_id=source_id,
                project_id=project_id,
                request_id=request_id,
                metadata={"is_primary": updated.is_primary},
            )
            return updated

    async def delete(
        self,
        *,
        project_id: UUID,
        source_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> CleanupJobRecord | None:
        async with self._database.session_scope() as session:
            if await self._projects.lock(session, project_id) is None:
                raise NotFoundError("Project was not found")
            source = await self._sources.lock_source(session, source_id)
            if source is None or source.project_id != project_id:
                raise NotFoundError("Source was not found")
            if await self._sources.has_build_references(session, source_id):
                raise ConflictError("A source referenced by an immutable Build cannot be deleted")
            cleanup_job = (
                await self._cleanup.capture_source_delete(
                    session,
                    project_id=project_id,
                    source_id=source_id,
                    actor_user_id=actor_user_id,
                    request_id=request_id,
                )
                if self._cleanup is not None
                else None
            )
            replacement = None
            if source.is_primary:
                replacement = await self._sources.first_versioned_executable(
                    session,
                    project_id,
                    exclude_source_id=source_id,
                )
            if not await self._sources.delete_source(session, source_id):
                raise NotFoundError("Source was not found")
            if replacement is not None:
                promoted = await self._sources.promote_executable(
                    session,
                    project_id=project_id,
                    source_id=replacement.id,
                )
                if promoted is None:
                    raise InvalidStateError("Replacement primary source became unavailable")
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="source.deleted",
                entity_type="project_source",
                entity_id=source_id,
                project_id=project_id,
                request_id=request_id,
                metadata={"cleanup_job_id": str(cleanup_job.id) if cleanup_job else None},
            )
        if cleanup_job is not None:
            cleanup = self._cleanup
            assert cleanup is not None
            cleanup.notify()
        return cleanup_job

    async def add_upload_version(
        self,
        *,
        project_id: UUID,
        source_id: UUID,
        content: AsyncReadable,
        media_type: str,
        filename: str | None,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> SourceVersionResult:
        source = await self._get_source(project_id, source_id)
        if source.origin_type is not SourceOrigin.UPLOAD:
            raise InvalidStateError("Upload versions can be added only to upload sources")
        operational = await self._settings.get_operational()
        max_bytes = (
            min(self._document_max_bytes, operational.max_upload_bytes)
            if source.kind is SourceKind.DOCUMENTATION
            else operational.max_upload_bytes
        )
        staged = await self._storage.stage_stream(
            f"projects/{project_id}/sources",
            content,
            max_bytes=max_bytes,
        )
        guard_id: UUID | None = None
        try:
            value = await self._storage.get_staged(staged, max_bytes=max_bytes)
            detected_format = _detect_format(
                source.kind,
                source.name,
                value,
                media_type,
                filename=filename,
            )
            guard_id = await self._arm_staged_guard(
                staged,
                project_id=project_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
            stored = await self._storage.commit_staged(staged)
        except BaseException:
            await self._storage.discard_staged(staged)
            if guard_id is not None:
                await self._release_guard(guard_id)
            raise
        try:
            result = await self._persist_version(
                source=source,
                content_sha256=stored.content_sha256,
                media_type=media_type,
                storage_key=stored.storage_key,
                byte_size=stored.byte_size,
                detected_format=detected_format,
                source_etag=None,
                source_last_modified=None,
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
        except BaseException:
            await self._release_guard(guard_id)
            raise
        await self._resolve_guard(guard_id)
        return result

    async def refresh(
        self,
        *,
        project_id: UUID,
        source_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> SourceVersionResult:
        source = await self._get_source(project_id, source_id)
        if source.origin_type is not SourceOrigin.URL or source.source_url is None:
            raise InvalidStateError("Only URL sources can be refreshed")
        latest = await self.latest_version(source_id)
        headers: dict[str, str] = {
            "Accept": (
                "application/json, application/yaml, text/*, application/pdf, "
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, "
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        }
        if latest and latest.source_etag:
            headers["If-None-Match"] = latest.source_etag
        if latest and latest.source_last_modified:
            headers["If-Modified-Since"] = latest.source_last_modified
        response = await self._http.fetch_bounded(
            source.source_url,
            policy=self._url_policy,
            max_bytes=self._fetch_max_bytes,
            max_redirects=self._fetch_max_redirects,
            headers=headers,
            max_attempts=self._fetch_max_attempts,
        )
        if response.status_code == 304:
            if latest is None:
                raise InvalidStateError(
                    "Remote source returned not-modified without a prior version"
                )
            return SourceVersionResult(latest, deduplicated=True)
        media_type = response.headers.get("Content-Type", "application/octet-stream")
        remote_name = PurePath(urlsplit(source.source_url).path).name or source.name
        detected_format = _detect_format(
            source.kind,
            source.name,
            response.body,
            media_type,
            filename=remote_name,
        )
        staged = await self._storage.stage_stream(
            f"projects/{project_id}/sources",
            BytesReader(response.body),
            max_bytes=self._fetch_max_bytes,
        )
        guard_id: UUID | None = None
        try:
            guard_id = await self._arm_staged_guard(
                staged,
                project_id=project_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
            stored = await self._storage.commit_staged(staged)
            result = await self._persist_version(
                source=source,
                content_sha256=stored.content_sha256,
                media_type=media_type,
                storage_key=stored.storage_key,
                byte_size=stored.byte_size,
                detected_format=detected_format,
                source_etag=response.headers.get("ETag"),
                source_last_modified=response.headers.get("Last-Modified"),
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
        except BaseException:
            await self._storage.discard_staged(staged)
            await self._release_guard(guard_id)
            raise
        await self._resolve_guard(guard_id)
        return result

    async def list_versions(self, project_id: UUID, source_id: UUID) -> list[SourceVersionRecord]:
        await self._get_source(project_id, source_id)
        async with self._database.session_scope() as session:
            return await self._sources.list_versions(session, source_id)

    async def list_versions_page(
        self,
        project_id: UUID,
        source_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SourceVersionRecord], int]:
        await self._get_source(project_id, source_id)
        async with self._database.session_scope() as session:
            return (
                await self._sources.list_versions(
                    session,
                    source_id,
                    limit=limit,
                    offset=offset,
                ),
                await self._sources.count_versions(session, source_id),
            )

    async def latest_version(self, source_id: UUID) -> SourceVersionRecord | None:
        async with self._database.session_scope() as session:
            return await self._sources.latest_version(session, source_id)

    async def get_version(self, version_id: UUID) -> SourceVersionRecord:
        async with self._database.session_scope() as session:
            version = await self._sources.get_version(session, version_id)
            if version is None:
                raise NotFoundError("Source version was not found")
            return version

    async def metadata(self, version_id: UUID) -> SourceVersionMetadataRecord:
        async with self._database.session_scope() as session:
            version = await self._sources.get_version(session, version_id)
            if version is None:
                raise NotFoundError("Source version was not found")
            source = await self._sources.get_source(session, version.source_id)
            if source is None:
                raise NotFoundError("Source was not found")
            build = await self._builds.latest_for_source_version(session, version.id)
            findings = await self._sources.list_findings_for_version(
                session,
                version.id,
                build_id=build.id if build is not None else None,
            )
            snapshot = (
                await self._snapshots.get(session, build.canonical_snapshot_id)
                if build is not None and build.canonical_snapshot_id is not None
                else None
            )
            generation = (
                await self._generations.get_for_build(session, build.id)
                if build is not None
                else None
            )
            config = (
                await self._builds.get_build_config(session, build.id)
                if build is not None
                else None
            )

        errors: list[SourceIssueRecord] = []
        parse_status: Literal["pending", "valid", "invalid"] = "pending"
        spec_version: str | None = None
        operation_count: int | None = None
        servers: list[str] = []
        auth_schemes: list[str] = []
        preview_markdown: str | None = None
        indexed_chunk_count: int | None = None

        if source.kind is SourceKind.DOCUMENTATION:
            if generation is not None:
                if generation.status is IndexGenerationStatus.READY:
                    parse_status = "valid"
                    chunks = [
                        chunk
                        for chunk in await self._read_document_chunks(
                            generation,
                            max_bytes=(
                                config.artifact_max_bytes
                                if config is not None
                                else max(self._document_max_bytes, self._fetch_max_bytes)
                            ),
                        )
                        if chunk.source_version_id == version.id
                    ]
                    indexed_chunk_count = len(chunks)
                    preview = "\n\n".join(chunk.text for chunk in chunks)
                    if preview:
                        preview_markdown = preview[:_PREVIEW_CHAR_LIMIT]
                        if len(preview) > _PREVIEW_CHAR_LIMIT:
                            preview_markdown += "\n\n[Preview truncated]"
                elif generation.status is IndexGenerationStatus.FAILED:
                    parse_status = "invalid"
                    errors.append(
                        SourceIssueRecord(
                            source_version_id=version.id,
                            stage="indexing",
                            code=(
                                build.error_code
                                if build is not None and build.error_code
                                else "INDEXING_ERROR"
                            ),
                            severity="error",
                            message=generation.error_summary or "Documentation indexing failed",
                        )
                    )
        elif findings:
            errors.extend(
                SourceIssueRecord(
                    source_version_id=finding.source_version_id,
                    stage=finding.stage,
                    code=finding.code,
                    severity=finding.severity,
                    message=finding.message,
                    pointer=finding.pointer,
                    line=finding.line,
                    column=finding.column,
                    details=finding.details,
                )
                for finding in findings
            )
            parse_status = (
                "invalid" if any(item.severity == "error" for item in errors) else "pending"
            )
        elif snapshot is not None:
            canonical = snapshot.canonical
            parse_status = "valid"
            spec_version = canonical.source_format
            operation_count = sum(
                operation.provenance.operation.source_version_id == version.id
                for operation in canonical.operations
            )
            servers = [
                str(server.url)
                for server in canonical.servers
                if server.source_ref.source_version_id == version.id
            ]
            auth_schemes = sorted(
                name
                for name, scheme in canonical.security_schemes.items()
                if scheme.source_ref.source_version_id == version.id
            )
        return SourceVersionMetadataRecord(
            version=version,
            parse_status=parse_status,
            spec_version=spec_version,
            operation_count=operation_count,
            servers=servers,
            auth_schemes=auth_schemes,
            errors=errors,
            preview_markdown=preview_markdown,
            indexed_chunk_count=indexed_chunk_count,
            embedding_model=generation.embedding_model if generation is not None else None,
            embedding_dimensions=generation.dimensions if generation is not None else None,
            index_status=generation.status if generation is not None else None,
            metadata_build_id=build.id if build is not None else None,
            index_generation_id=generation.id if generation is not None else None,
        )

    async def read_version(self, version_id: UUID) -> tuple[SourceVersionRecord, bytes]:
        version = await self.get_version(version_id)
        operational = await self._settings.get_operational()
        return version, await self._storage.get(
            version.storage_key,
            max_bytes=max(
                operational.max_upload_bytes,
                self._document_max_bytes,
                self._fetch_max_bytes,
            ),
        )

    def _normalize_source_definition(
        self,
        *,
        kind: SourceKind,
        name: str,
        origin_type: SourceOrigin,
        source_url: str | None,
        is_primary: bool,
    ) -> tuple[str, str | None]:
        normalized_name = name.strip()
        if not normalized_name:
            raise SourceParseError("Source name cannot be empty")
        normalized_url: str | None = None
        if origin_type is SourceOrigin.URL:
            if source_url is None:
                raise SourceParseError("URL source requires a source URL")
            normalized_url = self._url_policy.validate_syntax(source_url)[0]
        elif source_url is not None:
            raise SourceParseError("Uploaded source cannot define a source URL")
        if kind is SourceKind.DOCUMENTATION and is_primary:
            raise SourceParseError("Documentation sources cannot be executable primary sources")
        return normalized_name, normalized_url

    async def _existing_creation(
        self,
        *,
        source_id: UUID,
        project_id: UUID,
        kind: SourceKind,
        name: str,
        origin_type: SourceOrigin,
        source_url: str | None,
    ) -> SourceCreationResult | None:
        async with self._database.session_scope() as session:
            source = await self._sources.get_source(session, source_id)
            if source is None:
                return None
            self._assert_creation_identity(
                source,
                project_id=project_id,
                kind=kind,
                name=name,
                origin_type=origin_type,
                source_url=source_url,
            )
            version = await self._sources.latest_version(session, source_id)
            if version is None:
                return None
            return SourceCreationResult(source, version, deduplicated=True)

    @staticmethod
    def _assert_creation_identity(
        source: ProjectSourceRecord,
        *,
        project_id: UUID,
        kind: SourceKind,
        name: str,
        origin_type: SourceOrigin,
        source_url: str | None,
    ) -> None:
        if (
            source.project_id != project_id
            or source.kind is not kind
            or source.name != name
            or source.origin_type is not origin_type
            or source.source_url != source_url
        ):
            raise ConflictError("Source creation key was already used for different input")

    async def _persist_created_source(
        self,
        *,
        source_id: UUID,
        project_id: UUID,
        kind: SourceKind,
        name: str,
        origin_type: SourceOrigin,
        source_url: str | None,
        is_primary: bool,
        content_sha256: str,
        media_type: str,
        storage_key: str,
        byte_size: int,
        detected_format: str,
        source_etag: str | None,
        source_last_modified: str | None,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> SourceCreationResult:
        async with self._database.session_scope() as session:
            if self._cleanup is not None:
                await lock_object_reference(session, storage_key)
            if await self._projects.lock(session, project_id) is None:
                raise NotFoundError("Project was not found")
            source = await self._sources.get_source(session, source_id)
            if source is None:
                source = await self._sources.create_source(
                    session,
                    source_id=source_id,
                    project_id=project_id,
                    kind=kind,
                    name=name,
                    origin_type=origin_type,
                    source_url=source_url,
                    is_primary=False,
                )
                await self._audit.append(
                    session,
                    actor_user_id=actor_user_id,
                    event_type="source.created",
                    entity_type="project_source",
                    entity_id=source.id,
                    project_id=project_id,
                    request_id=request_id,
                    metadata={"kind": kind.value, "origin_type": origin_type.value},
                )
            else:
                self._assert_creation_identity(
                    source,
                    project_id=project_id,
                    kind=kind,
                    name=name,
                    origin_type=origin_type,
                    source_url=source_url,
                )
            version = await self._sources.get_version_by_hash(
                session,
                source.id,
                content_sha256,
            )
            deduplicated = version is not None
            if version is None:
                version = await self._sources.create_version(
                    session,
                    source_id=source.id,
                    content_sha256=content_sha256,
                    media_type=media_type[:200],
                    storage_key=storage_key,
                    byte_size=byte_size,
                    detected_format=detected_format,
                    source_etag=source_etag,
                    source_last_modified=source_last_modified,
                    created_by=actor_user_id,
                )
                await self._audit.append(
                    session,
                    actor_user_id=actor_user_id,
                    event_type="source.version_created",
                    entity_type="source_version",
                    entity_id=version.id,
                    project_id=project_id,
                    request_id=request_id,
                    metadata={
                        "source_id": str(source.id),
                        "content_sha256": content_sha256,
                        "byte_size": byte_size,
                        "detected_format": detected_format,
                    },
                )
            if kind in {SourceKind.OPENAPI, SourceKind.API_INVENTORY}:
                current_primary = await self._sources.get_versioned_primary_executable(
                    session,
                    project_id,
                )
                if is_primary or current_primary is None:
                    promoted = await self._sources.promote_executable(
                        session,
                        project_id=project_id,
                        source_id=source.id,
                    )
                    if promoted is None:
                        raise InvalidStateError("Executable source could not become primary")
                    source = promoted
                    if current_primary is None or current_primary.id != source.id:
                        await self._audit.append(
                            session,
                            actor_user_id=actor_user_id,
                            event_type="source.primary_promoted",
                            entity_type="project_source",
                            entity_id=source.id,
                            project_id=project_id,
                            request_id=request_id,
                        )
            return SourceCreationResult(
                source,
                version,
                deduplicated=deduplicated,
            )

    async def _get_source(self, project_id: UUID, source_id: UUID) -> ProjectSourceRecord:
        async with self._database.session_scope() as session:
            source = await self._sources.get_source(session, source_id)
            if source is None or source.project_id != project_id:
                raise NotFoundError("Source was not found")
            return source

    async def _persist_version(
        self,
        *,
        source: ProjectSourceRecord,
        content_sha256: str,
        media_type: str,
        storage_key: str,
        byte_size: int,
        detected_format: str,
        source_etag: str | None,
        source_last_modified: str | None,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> SourceVersionResult:
        async with self._database.session_scope() as session:
            if self._cleanup is not None:
                await lock_object_reference(session, storage_key)
            if await self._projects.lock(session, source.project_id) is None:
                raise NotFoundError("Project was not found")
            locked_source = await self._sources.lock_source(session, source.id)
            if locked_source is None or locked_source.project_id != source.project_id:
                raise NotFoundError("Source was not found")
            existing = await self._sources.get_version_by_hash(session, source.id, content_sha256)
            if existing is not None:
                if source.kind in {SourceKind.OPENAPI, SourceKind.API_INVENTORY}:
                    current_primary = await self._sources.get_versioned_primary_executable(
                        session,
                        source.project_id,
                    )
                    if current_primary is None:
                        promoted = await self._sources.promote_executable(
                            session,
                            project_id=source.project_id,
                            source_id=source.id,
                        )
                        if promoted is None:
                            raise InvalidStateError("Executable source could not become primary")
                return SourceVersionResult(existing, deduplicated=True)
            version = await self._sources.create_version(
                session,
                source_id=source.id,
                content_sha256=content_sha256,
                media_type=media_type[:200],
                storage_key=storage_key,
                byte_size=byte_size,
                detected_format=detected_format,
                source_etag=source_etag,
                source_last_modified=source_last_modified,
                created_by=actor_user_id,
            )
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="source.version_created",
                entity_type="source_version",
                entity_id=version.id,
                project_id=source.project_id,
                request_id=request_id,
                metadata={
                    "source_id": str(source.id),
                    "content_sha256": content_sha256,
                    "byte_size": byte_size,
                    "detected_format": detected_format,
                },
            )
            if source.kind in {SourceKind.OPENAPI, SourceKind.API_INVENTORY}:
                current_primary = await self._sources.get_versioned_primary_executable(
                    session,
                    source.project_id,
                )
                if current_primary is None:
                    promoted = await self._sources.promote_executable(
                        session,
                        project_id=source.project_id,
                        source_id=source.id,
                    )
                    if promoted is None:
                        raise InvalidStateError("Executable source could not become primary")
            return SourceVersionResult(version, deduplicated=False)

    async def _arm_staged_guard(
        self,
        staged: object,
        *,
        project_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> UUID | None:
        if self._cleanup is None:
            return None
        from app.clients.storage import StagedObject

        if not isinstance(staged, StagedObject):
            raise TypeError("Expected a staged storage object")
        return await self._cleanup.arm_orphan_guard(
            project_id=project_id,
            storage_key=self._storage.storage_key_for_staged(staged),
            actor_user_id=actor_user_id,
            request_id=request_id,
        )

    async def _release_guard(self, guard_id: UUID | None) -> None:
        if self._cleanup is not None and guard_id is not None:
            await self._cleanup.release_orphan_guard(guard_id)

    async def _resolve_guard(self, guard_id: UUID | None) -> None:
        if self._cleanup is not None and guard_id is not None:
            await self._cleanup.resolve_orphan_guard(guard_id)
