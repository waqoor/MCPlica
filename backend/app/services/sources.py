from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from mcp_contracts.json_types import JsonObject
from pydantic import TypeAdapter

from app.clients.database import DatabaseClient
from app.clients.http import HttpClient
from app.clients.storage import AsyncReadable
from app.core.exceptions import ConflictError, InvalidStateError, NotFoundError, SourceParseError
from app.core.network_policy import UrlPolicy
from app.domain.builds import BuildStatus
from app.domain.indexing import IndexGenerationStatus
from app.domain.sources import (
    ProjectSourceRecord,
    SourceIssueRecord,
    SourceKind,
    SourceOrigin,
    SourceVersionMetadataRecord,
    SourceVersionRecord,
)
from app.parsers.documentation import DocumentChunk, detect_office_document_format
from app.parsers.structured import parse_json_or_yaml
from app.providers.storage import ArtifactStorage
from app.repositories.audit import AuditRepository
from app.repositories.builds import BuildRepository
from app.repositories.canonical import CanonicalRepository
from app.repositories.indexing import IndexGenerationRepository
from app.repositories.projects import ProjectRepository
from app.repositories.sources import SourceRepository
from app.services.settings import OperationalSettingsProvider

_DOCUMENT_CHUNKS = TypeAdapter(list[DocumentChunk])
_PARSE_ERROR_CODES = frozenset(
    {"SOURCE_PARSE_ERROR", "REFERENCE_RESOLUTION_ERROR", "CANONICALIZATION_ERROR"}
)
_PREVIEW_CHAR_LIMIT = 20_000
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


@dataclass(frozen=True, slots=True)
class SourceVersionResult:
    version: SourceVersionRecord
    deduplicated: bool


def _parse_executable(value: bytes) -> tuple[str, JsonObject]:
    if value.startswith(b"PK\x03\x04"):
        raise SourceParseError("Archive uploads are not accepted as executable sources")
    detected, parsed = parse_json_or_yaml(value)
    return detected, parsed


def _detect_format(
    source: ProjectSourceRecord,
    value: bytes,
    media_type: str,
    *,
    filename: str | None = None,
) -> str:
    if not value:
        raise SourceParseError("Source content is empty")
    if source.kind in {SourceKind.OPENAPI, SourceKind.API_INVENTORY}:
        detected, parsed = _parse_executable(value)
        if source.kind is SourceKind.OPENAPI:
            version = str(parsed.get("openapi", ""))
            if not (version.startswith("3.0.") or version.startswith("3.1.")):
                raise SourceParseError("OpenAPI source must declare supported 3.0.x or 3.1.x")
        elif parsed.get("schema") != "api-inventory/v1":
            raise SourceParseError("API Inventory source must declare schema api-inventory/v1")
        return detected

    normalized_media = media_type.partition(";")[0].strip().casefold()
    name = (filename or source.name).strip().casefold()
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
        document_max_bytes: int,
        fetch_max_bytes: int,
        fetch_max_redirects: int,
        fetch_max_attempts: int,
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
        self._document_max_bytes = document_max_bytes
        self._fetch_max_bytes = fetch_max_bytes
        self._fetch_max_redirects = fetch_max_redirects
        self._fetch_max_attempts = fetch_max_attempts

    async def list(self, project_id: UUID) -> list[ProjectSourceRecord]:
        async with self._database.session_scope() as session:
            if await self._projects.get(session, project_id) is None:
                raise NotFoundError("Project was not found")
            return await self._sources.list_sources(session, project_id)

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
        async with self._database.session_scope() as session:
            if await self._projects.lock(session, project_id) is None:
                raise NotFoundError("Project was not found")
            if is_primary and await self._sources.get_primary_executable(session, project_id):
                raise ConflictError("A primary executable source already exists")
            source = await self._sources.create_source(
                session,
                project_id=project_id,
                kind=kind,
                name=normalized_name,
                origin_type=origin_type,
                source_url=normalized_url,
                is_primary=is_primary,
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
        try:
            value = await self._storage.get_staged(staged, max_bytes=max_bytes)
            detected_format = _detect_format(
                source,
                value,
                media_type,
                filename=filename,
            )
            stored = await self._storage.commit_staged(staged)
        except BaseException:
            await self._storage.discard_staged(staged)
            raise
        return await self._persist_version(
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
            source,
            response.body,
            media_type,
            filename=remote_name,
        )
        stored = await self._storage.put_bytes(
            f"projects/{project_id}/sources",
            response.body,
            max_bytes=self._fetch_max_bytes,
        )
        return await self._persist_version(
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

    async def list_versions(self, project_id: UUID, source_id: UUID) -> list[SourceVersionRecord]:
        await self._get_source(project_id, source_id)
        async with self._database.session_scope() as session:
            return await self._sources.list_versions(session, source_id)

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
                    if generation.chunk_manifest_storage_key is None:
                        raise InvalidStateError("Ready index generation has no chunk manifest")
                    manifest = await self._storage.get(
                        generation.chunk_manifest_storage_key,
                        max_bytes=(
                            config.artifact_max_bytes
                            if config is not None
                            else max(self._document_max_bytes, self._fetch_max_bytes)
                        ),
                    )
                    chunks = [
                        chunk
                        for chunk in _DOCUMENT_CHUNKS.validate_json(manifest)
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
                            code=(
                                build.error_code
                                if build is not None and build.error_code
                                else "INDEXING_ERROR"
                            ),
                            severity="error",
                            message=generation.error_summary or "Documentation indexing failed",
                        )
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
        elif (
            build is not None
            and build.status is BuildStatus.FAILED
            and build.error_code in _PARSE_ERROR_CODES
        ):
            parse_status = "invalid"
            errors.append(
                SourceIssueRecord(
                    code=build.error_code,
                    severity="error",
                    message=build.error_summary or "Source parsing failed",
                )
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
            locked_source = await self._sources.lock_source(session, source.id)
            if locked_source is None or locked_source.project_id != source.project_id:
                raise NotFoundError("Source was not found")
            existing = await self._sources.get_version_by_hash(session, source.id, content_sha256)
            if existing is not None:
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
            return SourceVersionResult(version, deduplicated=False)
