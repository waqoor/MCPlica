import asyncio
import hashlib
import time
from uuid import UUID

from mcp_contracts import CanonicalApi, DocumentationRef

from app.clients.database import DatabaseClient
from app.core.canonical_json import canonical_sha256
from app.core.exceptions import NotFoundError, SourceParseError
from app.domain.canonicalization import CanonicalSnapshotRecord
from app.domain.projects import ProjectRoutingConfiguration
from app.domain.sources import BoundSourceVersionRecord, SourceKind
from app.parsers.api_inventory import parse_api_inventory
from app.parsers.openapi.parser import ExternalOpenApiDocument, parse_openapi
from app.parsers.structured import parse_json_or_yaml
from app.providers.storage import ArtifactStorage
from app.repositories.canonical import CanonicalRepository
from app.repositories.projects import ProjectRepository
from app.repositories.sources import SourceRepository


def _attribute_source_error(
    exc: SourceParseError,
    source_version_id: UUID,
    *,
    pointer: str | None = None,
) -> None:
    """Attach immutable source identity without overwriting deeper parser evidence."""

    exc.details.setdefault("source_version_id", str(source_version_id))
    if pointer is not None and not any(
        key in exc.details for key in ("source_pointer", "source_location", "pointer")
    ):
        exc.details["source_pointer"] = pointer


_FAILURE_COOLDOWN_SECONDS = 15.0

_CacheKey = tuple[UUID, str, str | None, str | None, tuple[tuple[str, str], ...]]


def _source_fingerprint(bindings: list[BoundSourceVersionRecord]) -> str:
    digest = hashlib.sha256()
    for binding in sorted(bindings, key=lambda item: str(item.version.id)):
        digest.update(str(binding.version.id).encode())
        digest.update(b"\x00")
        digest.update(binding.version.content_sha256.encode())
        digest.update(b"\n")
    return digest.hexdigest()


class CanonicalizationService:
    def __init__(
        self,
        database: DatabaseClient,
        projects: ProjectRepository,
        sources: SourceRepository,
        snapshots: CanonicalRepository,
        storage: ArtifactStorage,
    ) -> None:
        self._database = database
        self._projects = projects
        self._sources = sources
        self._snapshots = snapshots
        self._storage = storage
        # Avoids re-validating unchanged input on every 2s /journey poll.
        self._cache: dict[_CacheKey, CanonicalApi] = {}
        # Holds a failed attempt's error briefly so it isn't retried instantly.
        self._failures: dict[_CacheKey, tuple[float, BaseException]] = {}
        # Coalesces concurrent retries for the same input onto one computation.
        self._inflight: dict[_CacheKey, asyncio.Future[CanonicalApi]] = {}

    async def current_source_versions(self, project_id: UUID) -> list[UUID]:
        return [binding.version.id for binding in await self.current_source_bindings(project_id)]

    async def current_source_bindings(
        self,
        project_id: UUID,
    ) -> list[BoundSourceVersionRecord]:
        async with self._database.session_scope() as session:
            if await self._projects.get(session, project_id) is None:
                raise NotFoundError("Project was not found")
            return await self._sources.latest_bound_versions(session, project_id)

    async def canonicalize(
        self,
        project_id: UUID,
        bindings: list[BoundSourceVersionRecord],
        *,
        max_source_bytes: int,
        routing: ProjectRoutingConfiguration | None = None,
    ) -> CanonicalApi:
        source_version_ids = [binding.version.id for binding in bindings]
        if len(set(source_version_ids)) != len(source_version_ids):
            raise SourceParseError("Source version bindings must be unique")
        async with self._database.session_scope() as session:
            project = await self._projects.get(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
        if any(binding.source.project_id != project_id for binding in bindings):
            raise SourceParseError("One or more source versions do not belong to the Project")
        if any(not binding.binding_metadata_trustworthy for binding in bindings):
            raise SourceParseError(
                "Historical Build source identity cannot be proven; create a new Build",
                details={"reason_code": "BUILD_SOURCE_BINDINGS_UNTRUSTWORTHY"},
            )
        effective_routing = routing or ProjectRoutingConfiguration(
            default_base_url=project.default_base_url,
            active_server_ref=project.active_server_ref,
            server_mappings=project.server_mappings,
        )
        cache_key = (
            project_id,
            _source_fingerprint(bindings),
            effective_routing.default_base_url,
            effective_routing.active_server_ref,
            tuple(sorted(effective_routing.server_mappings.items())),
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        pending_failure = self._failures.get(cache_key)
        if pending_failure is not None:
            failed_at, exc = pending_failure
            if time.monotonic() - failed_at < _FAILURE_COOLDOWN_SECONDS:
                raise exc
            del self._failures[cache_key]
        existing = self._inflight.get(cache_key)
        if existing is not None:
            try:
                return await existing
            except asyncio.CancelledError:
                if asyncio.current_task().cancelling():
                    raise
                # The in-flight leader was cancelled, not us; retry as the new leader.
                return await self.canonicalize(
                    project_id,
                    bindings,
                    max_source_bytes=max_source_bytes,
                    routing=routing,
                )
        future: asyncio.Future[CanonicalApi] = asyncio.get_running_loop().create_future()
        self._inflight[cache_key] = future
        try:
            result = await self._canonicalize_uncached(
                project_id,
                bindings,
                source_version_ids=source_version_ids,
                effective_routing=effective_routing,
                max_source_bytes=max_source_bytes,
            )
        except BaseException as exc:
            del self._inflight[cache_key]
            if isinstance(exc, Exception):
                self._failures[cache_key] = (time.monotonic(), exc)
                future.set_exception(exc)
                future.exception()  # mark retrieved so asyncio doesn't warn if nobody awaits it
            else:
                future.cancel()
            raise
        self._failures.pop(cache_key, None)
        self._cache[cache_key] = result
        future.set_result(result)
        del self._inflight[cache_key]
        return result

    async def _canonicalize_uncached(
        self,
        project_id: UUID,
        bindings: list[BoundSourceVersionRecord],
        *,
        source_version_ids: list[UUID],
        effective_routing: ProjectRoutingConfiguration,
        max_source_bytes: int,
    ) -> CanonicalApi:
        primary = [
            item
            for item in bindings
            if item.source.is_primary
            and item.source.kind in {SourceKind.OPENAPI, SourceKind.API_INVENTORY}
        ]
        if len(primary) != 1:
            raise SourceParseError("A build requires exactly one primary executable source")
        # Reads one dependency at a time to avoid holding every source's bytes in memory.
        root = primary[0]
        root_payload = await self._storage.get(root.version.storage_key, max_bytes=max_source_bytes)
        try:
            # CPU-bound; run off the event loop so it can't block other requests.
            _, document = await asyncio.to_thread(parse_json_or_yaml, root_payload)
            del root_payload
        except SourceParseError as exc:
            _attribute_source_error(exc, root.version.id, pointer="#")
            raise
        if root.source.kind is SourceKind.OPENAPI:
            external_documents: dict[str, ExternalOpenApiDocument] = {}
            for binding in bindings:
                if (
                    binding.version.id == root.version.id
                    or binding.source.kind is not SourceKind.OPENAPI
                ):
                    continue
                dependency_payload = await self._storage.get(
                    binding.version.storage_key, max_bytes=max_source_bytes
                )
                try:
                    _, external = await asyncio.to_thread(parse_json_or_yaml, dependency_payload)
                    del dependency_payload
                except SourceParseError as exc:
                    _attribute_source_error(exc, binding.version.id, pointer="#")
                    raise
                captured = ExternalOpenApiDocument(external, binding.version.id)
                for key in binding.effective_dependency_aliases:
                    if key in external_documents:
                        raise SourceParseError(
                            f"Ambiguous external OpenAPI dependency name: {key}",
                            details={
                                "source_version_id": str(binding.version.id),
                                "source_pointer": "#",
                            },
                        )
                    external_documents[key] = captured
            try:
                canonical = await asyncio.to_thread(
                    parse_openapi,
                    document,
                    project_id=project_id,
                    source_version_id=root.version.id,
                    content_sha256=root.version.content_sha256,
                    active_server_ref=effective_routing.active_server_ref,
                    server_mappings=effective_routing.server_mappings,
                    default_base_url=effective_routing.default_base_url,
                    external_documents=external_documents,
                )
            except SourceParseError as exc:
                _attribute_source_error(exc, root.version.id, pointer="#")
                raise
        else:
            try:
                canonical = await asyncio.to_thread(
                    parse_api_inventory,
                    document,
                    project_id=project_id,
                    source_version_id=root.version.id,
                    content_sha256=root.version.content_sha256,
                    active_server_ref=effective_routing.active_server_ref,
                    server_mappings=effective_routing.server_mappings,
                    default_base_url=effective_routing.default_base_url,
                )
            except SourceParseError as exc:
                _attribute_source_error(exc, root.version.id, pointer="#")
                raise
        documentation_refs = [
            DocumentationRef(
                source_version_id=item.version.id,
                content_sha256=item.version.content_sha256,
                title=item.source.name,
            )
            for item in bindings
            if item.source.kind is SourceKind.DOCUMENTATION
        ]
        return canonical.model_copy(
            update={
                "documentation_refs": documentation_refs,
                "provenance": canonical.provenance.model_copy(
                    update={
                        "source_version_ids": sorted(source_version_ids, key=str),
                        "source_fingerprint": _source_fingerprint(bindings),
                    }
                ),
            }
        )

    async def create_snapshot(
        self,
        project_id: UUID,
        bindings: list[BoundSourceVersionRecord],
        *,
        max_source_bytes: int,
        routing: ProjectRoutingConfiguration | None = None,
    ) -> CanonicalSnapshotRecord:
        canonical = await self.canonicalize(
            project_id,
            bindings,
            max_source_bytes=max_source_bytes,
            routing=routing,
        )
        digest = canonical_sha256(canonical)
        async with self._database.session_scope() as session:
            return await self._snapshots.create(
                session,
                project_id=project_id,
                canonical=canonical,
                canonical_sha256=digest,
                source_version_ids=sorted(
                    (binding.version.id for binding in bindings),
                    key=str,
                ),
            )

    async def get_snapshot(self, snapshot_id: UUID) -> CanonicalSnapshotRecord:
        async with self._database.session_scope() as session:
            snapshot = await self._snapshots.get(session, snapshot_id)
            if snapshot is None:
                raise NotFoundError("Canonical snapshot was not found")
            return snapshot
