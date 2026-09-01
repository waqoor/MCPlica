import hashlib
from pathlib import PurePosixPath
from urllib.parse import urlsplit
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

    async def current_source_versions(self, project_id: UUID) -> list[UUID]:
        async with self._database.session_scope() as session:
            if await self._projects.get(session, project_id) is None:
                raise NotFoundError("Project was not found")
            bindings = await self._sources.latest_bound_versions(session, project_id)
        return [binding.version.id for binding in bindings]

    async def canonicalize(
        self,
        project_id: UUID,
        source_version_ids: list[UUID],
        *,
        max_source_bytes: int,
        routing: ProjectRoutingConfiguration | None = None,
    ) -> CanonicalApi:
        if len(set(source_version_ids)) != len(source_version_ids):
            raise SourceParseError("Source version bindings must be unique")
        async with self._database.session_scope() as session:
            project = await self._projects.get(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
            bindings = await self._sources.list_bound_versions(
                session,
                project_id,
                source_version_ids,
            )
        if len(bindings) != len(source_version_ids):
            raise SourceParseError("One or more source versions do not belong to the Project")
        effective_routing = routing or ProjectRoutingConfiguration(
            default_base_url=project.default_base_url,
            active_server_ref=project.active_server_ref,
            server_mappings=project.server_mappings,
        )
        primary = [
            item
            for item in bindings
            if item.source.is_primary
            and item.source.kind in {SourceKind.OPENAPI, SourceKind.API_INVENTORY}
        ]
        if len(primary) != 1:
            raise SourceParseError("A build requires exactly one primary executable source")
        # Documentation contributes immutable metadata here; its payload belongs
        # exclusively to the bounded indexing parser. Read executable dependencies
        # one at a time instead of retaining every source's raw bytes concurrently.
        root = primary[0]
        root_payload = await self._storage.get(root.version.storage_key, max_bytes=max_source_bytes)
        try:
            _, document = parse_json_or_yaml(root_payload)
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
                    _, external = parse_json_or_yaml(dependency_payload)
                    del dependency_payload
                except SourceParseError as exc:
                    _attribute_source_error(exc, binding.version.id, pointer="#")
                    raise
                captured = ExternalOpenApiDocument(external, binding.version.id)
                keys = {binding.source.name}
                if binding.source.source_url:
                    keys.add(binding.source.source_url)
                    path_name = PurePosixPath(urlsplit(binding.source.source_url).path).name
                    if path_name:
                        keys.add(path_name)
                for key in keys:
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
                canonical = parse_openapi(
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
                canonical = parse_api_inventory(
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
        source_version_ids: list[UUID],
        *,
        max_source_bytes: int,
        routing: ProjectRoutingConfiguration | None = None,
    ) -> CanonicalSnapshotRecord:
        canonical = await self.canonicalize(
            project_id,
            source_version_ids,
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
                source_version_ids=sorted(source_version_ids, key=str),
            )

    async def get_snapshot(self, snapshot_id: UUID) -> CanonicalSnapshotRecord:
        async with self._database.session_scope() as session:
            snapshot = await self._snapshots.get(session, snapshot_id)
            if snapshot is None:
                raise NotFoundError("Canonical snapshot was not found")
            return snapshot
