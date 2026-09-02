import hashlib
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, Literal, cast
from uuid import UUID

import pytest

from app.domain.sources import (
    ProjectSourceRecord,
    SourceFindingRecord,
    SourceKind,
    SourceOrigin,
    SourceVersionRecord,
)
from app.parsers.openapi.parser import parse_openapi
from app.services.sources import SourceService


class _Database:
    @asynccontextmanager
    async def session_scope(self):
        yield object()


class _Sources:
    def __init__(
        self,
        source: ProjectSourceRecord,
        version: SourceVersionRecord,
        findings: list[SourceFindingRecord],
    ) -> None:
        self.source = source
        self.version = version
        self.findings = findings

    async def get_version(self, _session: object, _version_id: UUID):
        return self.version

    async def get_source(self, _session: object, _source_id: UUID):
        return self.source

    async def list_findings_for_version(self, _session: object, *_args: object, **_kwargs: object):
        return self.findings


class _Builds:
    async def latest_for_source_version(self, _session: object, _version_id: UUID):
        return SimpleNamespace(id=UUID(int=4), canonical_snapshot_id=UUID(int=5))

    async def get_build_config(self, _session: object, _build_id: UUID):
        return None


class _Snapshots:
    def __init__(self, canonical: object) -> None:
        self.canonical = canonical

    async def get(self, _session: object, _snapshot_id: UUID):
        return SimpleNamespace(canonical=self.canonical)


class _Generations:
    async def get_for_build(self, _session: object, _build_id: UUID):
        return None


def _service(severity: Literal["warning", "info", "error"] | None) -> SourceService:
    now = datetime(2026, 9, 2, tzinfo=UTC)
    source = ProjectSourceRecord(
        id=UUID(int=1),
        project_id=UUID(int=2),
        kind=SourceKind.OPENAPI,
        name="openapi.json",
        origin_type=SourceOrigin.UPLOAD,
        source_url=None,
        is_primary=True,
        created_at=now,
        current_version_id=UUID(int=3),
        current_version_selected_at=now,
    )
    version = SourceVersionRecord(
        id=UUID(int=3),
        source_id=source.id,
        content_sha256=hashlib.sha256(b"source").hexdigest(),
        media_type="application/json",
        storage_key="source/openapi.json",
        byte_size=100,
        detected_format="json",
        source_etag=None,
        source_last_modified=None,
        created_by=UUID(int=9),
        created_at=now,
    )
    canonical = parse_openapi(
        {
            "openapi": "3.1.0",
            "info": {"title": "Metadata", "version": "1"},
            "servers": [{"url": "https://api.example.test"}],
            "paths": {
                "/items": {
                    "get": {
                        "operationId": "listItems",
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
        },
        project_id=source.project_id,
        source_version_id=version.id,
        content_sha256=version.content_sha256,
    )
    findings = (
        []
        if severity is None
        else [
            SourceFindingRecord(
                id=UUID(int=10),
                build_id=UUID(int=4),
                source_version_id=version.id,
                stage="parsing",
                code="TEST_FINDING",
                severity=severity,
                message="test finding",
                created_at=now,
            )
        ]
    )
    return SourceService(
        cast(Any, _Database()),
        cast(Any, _Sources(source, version, findings)),
        cast(Any, object()),
        cast(Any, _Builds()),
        cast(Any, _Snapshots(canonical)),
        cast(Any, _Generations()),
        cast(Any, object()),
        cast(Any, object()),
        cast(Any, object()),
        cast(Any, object()),
        cast(Any, object()),
        canonicalization=None,
        document_max_bytes=1_000_000,
        fetch_max_bytes=1_000_000,
        fetch_max_redirects=1,
        fetch_max_attempts=1,
    )


@pytest.mark.parametrize(
    ("severity", "expected_status"),
    [(None, "valid"), ("info", "valid"), ("warning", "valid"), ("error", "invalid")],
)
async def test_snapshot_metadata_is_independent_of_finding_severity(
    severity: Literal["warning", "info", "error"] | None,
    expected_status: str,
) -> None:
    metadata = await _service(severity).metadata(UUID(int=3))

    assert metadata.parse_status == expected_status
    assert metadata.operation_count == 1
    assert metadata.spec_version == "openapi-3.1"
    assert metadata.servers == ["https://api.example.test/"]
    assert [finding.severity for finding in metadata.errors] == (
        [] if severity is None else [severity]
    )
