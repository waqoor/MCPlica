from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from mcp_contracts.json_types import JsonObject

from app.clients.database import DatabaseClient
from app.clients.http import HttpClient
from app.clients.storage import AsyncReadable
from app.core.exceptions import ConflictError, InvalidStateError, NotFoundError, SourceParseError
from app.core.network_policy import UrlPolicy
from app.domain.sources import (
    ProjectSourceRecord,
    SourceKind,
    SourceOrigin,
    SourceVersionRecord,
)
from app.parsers.structured import parse_json_or_yaml
from app.providers.storage import ArtifactStorage
from app.repositories.audit import AuditRepository
from app.repositories.projects import ProjectRepository
from app.repositories.sources import SourceRepository
from app.services.settings import OperationalSettingsProvider


@dataclass(frozen=True, slots=True)
class SourceVersionResult:
    version: SourceVersionRecord
    deduplicated: bool


def _parse_executable(value: bytes) -> tuple[str, JsonObject]:
    if value.startswith(b"PK\x03\x04"):
        raise SourceParseError("Archive uploads are not accepted as executable sources")
    detected, parsed = parse_json_or_yaml(value)
    return detected, parsed


def _detect_format(source: ProjectSourceRecord, value: bytes, media_type: str) -> str:
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
    name = source.name.casefold()
    if value.startswith(b"%PDF-") or normalized_media == "application/pdf" or name.endswith(".pdf"):
        if not value.startswith(b"%PDF-"):
            raise SourceParseError("PDF documentation does not contain a valid PDF header")
        return "pdf"
    try:
        value.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceParseError("Documentation must be UTF-8 text or a valid PDF") from exc
    if normalized_media in {"text/html", "application/xhtml+xml"} or name.endswith(
        (".html", ".htm")
    ):
        return "html"
    if normalized_media in {"text/markdown", "text/x-markdown"} or name.endswith(
        (".md", ".markdown")
    ):
        return "markdown"
    if normalized_media.startswith("text/") or name.endswith(".txt"):
        return "text"
    raise SourceParseError("Unsupported documentation media type")


class SourceService:
    def __init__(
        self,
        database: DatabaseClient,
        sources: SourceRepository,
        projects: ProjectRepository,
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
            detected_format = _detect_format(source, value, media_type)
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
            "Accept": "application/json, application/yaml, text/*, application/pdf"
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
        detected_format = _detect_format(source, response.body, media_type)
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
