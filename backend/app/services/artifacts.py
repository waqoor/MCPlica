import asyncio
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from typing import cast

from mcp_contracts import MCPManifest, MCPResource

from app.core.canonical_json import canonical_json_bytes
from app.core.exceptions import InvalidStateError, PackagingError
from app.domain.builds import BuildConfiguration, BuildRecord
from app.domain.indexing import DocumentIndexGenerationRecord
from app.domain.validation import ValidationReportRecord
from app.parsers.documentation import DocumentChunk
from app.providers.storage import ArtifactStorage


@dataclass(frozen=True, slots=True)
class StoredBuildArtifact:
    storage_key: str
    sha256: str
    byte_size: int


class ArtifactService:
    def __init__(self, storage: ArtifactStorage) -> None:
        self._storage = storage

    async def documentation_resources(
        self,
        generation: DocumentIndexGenerationRecord,
        *,
        project_slug: str,
        max_bytes: int,
    ) -> list[MCPResource]:
        if not generation.chunk_manifest_storage_key:
            raise PackagingError("Index generation has no durable documentation chunk artifact")
        value = await self._storage.get(
            generation.chunk_manifest_storage_key,
            max_bytes=max_bytes,
        )
        if hashlib.sha256(value).hexdigest() != generation.chunk_manifest_sha256:
            raise PackagingError("Documentation chunk artifact hash verification failed")
        try:
            raw = json.loads(value)
            if not isinstance(raw, list):
                raise TypeError
            chunks = [DocumentChunk.model_validate(item) for item in cast(list[object], raw)]
        except (TypeError, ValueError) as exc:
            raise PackagingError("Documentation chunk artifact is malformed") from exc
        return [
            MCPResource(
                uri=(f"docs://{project_slug}/{chunk.source_version_id}/{chunk.chunk_id}"),
                name=(
                    " / ".join(chunk.section_path)
                    if chunk.title is None
                    else f"{chunk.title}: {' / '.join(chunk.section_path)}"
                ),
                description="Source-derived project documentation excerpt",
                content=chunk.text,
                provenance={
                    "source_version_id": str(chunk.source_version_id),
                    "chunk_id": chunk.chunk_id,
                    "content_sha256": chunk.content_sha256,
                },
            )
            for chunk in chunks
        ]

    async def store_manifest(
        self,
        manifest: MCPManifest,
        *,
        max_bytes: int,
    ) -> StoredBuildArtifact:
        value = canonical_json_bytes(manifest)
        stored = await self._storage.put_bytes(
            "build-manifests",
            value,
            max_bytes=max_bytes,
        )
        return StoredBuildArtifact(
            storage_key=stored.storage_key,
            sha256=stored.content_sha256,
            byte_size=stored.byte_size,
        )

    async def package(
        self,
        *,
        build: BuildRecord,
        config: BuildConfiguration,
        manifest: MCPManifest,
        validation: ValidationReportRecord,
        project_name: str,
        project_slug: str,
        source_version_ids: list[str],
    ) -> StoredBuildArtifact:
        if validation.overall_status.value != "pass" or validation.blocking_error_count:
            raise InvalidStateError("A failing validation report cannot be packaged")
        manifest_bytes = canonical_json_bytes(manifest)
        metadata_bytes = canonical_json_bytes(
            {
                "schema_version": "mcplica-build-metadata/v1",
                "build_id": str(build.id),
                "project_id": str(build.project_id),
                "project_name": project_name,
                "project_slug": project_slug,
                "sequence": build.sequence,
                "trigger": build.trigger.value,
                "source_version_ids": sorted(source_version_ids),
                "canonical_snapshot_id": (
                    str(build.canonical_snapshot_id)
                    if build.canonical_snapshot_id is not None
                    else None
                ),
                "compiler_version": build.compiler_version,
                "manifest_schema_version": build.manifest_schema_version,
                "runtime_compatibility": build.runtime_compatibility,
                "models": {
                    "analysis": build.analysis_model,
                    "validation": build.validation_model,
                    "embedding": build.embedding_model,
                    "embedding_dimensions": build.embedding_dimensions,
                },
                "prompt_bundle_version": build.prompt_bundle_version,
                "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "excluded_operation_keys": sorted(
                    item.operation_key for item in config.excluded_operations
                ),
                "created_at": build.created_at.isoformat(),
            }
        )
        validation_bytes = canonical_json_bytes(validation.model_dump(mode="json", by_alias=True))
        readme = _readme(project_name, project_slug, build).encode()
        compose_example = _compose_example(
            project_slug,
            hashlib.sha256(manifest_bytes).hexdigest(),
        ).encode()
        files = {
            "README.md": readme,
            "build-metadata.json": metadata_bytes,
            "compose.example.yaml": compose_example,
            "manifest.json": manifest_bytes,
            "validation-report.json": validation_bytes,
        }
        value = await asyncio.to_thread(_deterministic_zip, files)
        stored = await self._storage.put_bytes(
            "build-exports",
            value,
            max_bytes=config.artifact_max_bytes,
        )
        return StoredBuildArtifact(
            storage_key=stored.storage_key,
            sha256=stored.content_sha256,
            byte_size=stored.byte_size,
        )

    async def read_manifest(self, build: BuildRecord, *, max_bytes: int) -> bytes:
        if not build.manifest_storage_key or not build.manifest_sha256:
            raise InvalidStateError("Build has no compiled manifest")
        value = await self._storage.get(build.manifest_storage_key, max_bytes=max_bytes)
        if hashlib.sha256(value).hexdigest() != build.manifest_sha256:
            raise PackagingError("Stored manifest hash verification failed")
        return value

    async def read_export(self, build: BuildRecord, *, max_bytes: int) -> bytes:
        if not build.artifact_storage_key or not build.artifact_sha256:
            raise InvalidStateError("Build has no export artifact")
        value = await self._storage.get(build.artifact_storage_key, max_bytes=max_bytes)
        if hashlib.sha256(value).hexdigest() != build.artifact_sha256:
            raise PackagingError("Stored export hash verification failed")
        return value


def _deterministic_zip(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, files[name])
    return output.getvalue()


def _readme(project_name: str, project_slug: str, build: BuildRecord) -> str:
    return (
        f"# {project_name} MCPlica Build\n\n"
        f"Immutable Build `{build.id}` (project `{project_slug}`, sequence {build.sequence}).\n\n"
        "This bundle contains project-specific generated configuration only. It contains no "
        "plaintext upstream credentials or MCP access secrets. Run it with a separately installed "
        "compatible MCPlica generic runtime and provide the required read-only secret bundle via "
        "that runtime's documented secret mount. Verify `manifest.json` and "
        "`validation-report.json` before use. `compose.example.yaml` is a hardened starting "
        "fragment; set its image to an immutable compatible runtime digest and provide the "
        "secret-bundle host path outside this export.\n"
    )


def _compose_example(project_slug: str, manifest_sha256: str) -> str:
    return (
        "services:\n"
        f"  {project_slug}-mcp:\n"
        "    image: ${RUNTIME_IMAGE:?Set an immutable runtime image digest}\n"
        '    user: "10001:10001"\n'
        "    init: true\n"
        "    restart: unless-stopped\n"
        "    read_only: true\n"
        "    cap_drop: [ALL]\n"
        "    pids_limit: 256\n"
        "    mem_limit: 512m\n"
        "    cpus: 1.0\n"
        "    security_opt:\n"
        "      - no-new-privileges:true\n"
        "    environment:\n"
        '      MCP_ENVIRONMENT: "production"\n'
        '      MCP_MANIFEST_PATH: "/runtime/manifest.json"\n'
        f'      MCP_MANIFEST_SHA256: "{manifest_sha256}"\n'
        '      MCP_SECRET_BUNDLE_PATH: "/run/secrets/mcplica-runtime.json"\n'
        "      MCP_PUBLIC_BASE_URL: ${MCP_PUBLIC_BASE_URL:?Set the public MCP URL}\n"
        "      MCP_ALLOWED_HOSTS: ${MCP_ALLOWED_HOSTS:?Set the exact public host}\n"
        '      MCP_TLS_VERIFY: "true"\n'
        '      MCP_TRUST_ENVIRONMENT_PROXY: "false"\n'
        '      MCP_REQUIRE_SECURE_SECRET_PERMISSIONS: "true"\n'
        "    volumes:\n"
        "      - ./manifest.json:/runtime/manifest.json:ro\n"
        "      - ${SECRET_BUNDLE_HOST_PATH:?Set the secret bundle host path}:"
        "/run/secrets/mcplica-runtime.json:ro\n"
        "    tmpfs:\n"
        "      - /tmp:size=64m,mode=1777\n"
    )
