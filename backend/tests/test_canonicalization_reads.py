import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID

from app.domain.sources import (
    BoundSourceVersionRecord,
    ProjectSourceRecord,
    SourceKind,
    SourceOrigin,
    SourceVersionRecord,
)
from app.services.canonicalization.service import CanonicalizationService


class _Database:
    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[object]:
        yield object()


def _binding(number: int, kind: SourceKind, *, primary: bool = False) -> BoundSourceVersionRecord:
    now = datetime.now(UTC)
    return BoundSourceVersionRecord(
        source=ProjectSourceRecord(
            id=UUID(int=number),
            project_id=UUID(int=1),
            kind=kind,
            name=f"source-{number}",
            origin_type=SourceOrigin.UPLOAD,
            source_url=None,
            is_primary=primary,
            created_at=now,
        ),
        version=SourceVersionRecord(
            id=UUID(int=number + 100),
            source_id=UUID(int=number),
            content_sha256="a" * 64,
            media_type="application/json",
            storage_key=f"source-{number}",
            byte_size=1,
            detected_format="json",
            source_etag=None,
            source_last_modified=None,
            created_by=UUID(int=2),
            created_at=now,
        ),
    )


async def test_canonicalization_never_reads_documentation_payloads() -> None:
    root = _binding(10, SourceKind.OPENAPI, primary=True)
    documentation = [_binding(number, SourceKind.DOCUMENTATION) for number in range(11, 31)]
    bindings = [root, *documentation]
    source = {
        "openapi": "3.1.0",
        "info": {"title": "Example", "version": "1"},
        "servers": [{"url": "https://api.example.com"}],
        "paths": {"/records": {"get": {"responses": {"200": {"description": "OK"}}}}},
    }

    async def read(key: str, *, max_bytes: int) -> bytes:
        assert key == root.version.storage_key, "documentation body reached canonicalization"
        assert max_bytes == 10_000
        return json.dumps(source).encode()

    storage = SimpleNamespace(get=AsyncMock(side_effect=read))
    project = SimpleNamespace(default_base_url=None, active_server_ref=None, server_mappings={})
    service = CanonicalizationService(
        cast(Any, _Database()),
        cast(Any, SimpleNamespace(get=AsyncMock(return_value=project))),
        cast(Any, SimpleNamespace(list_bound_versions=AsyncMock(return_value=bindings))),
        cast(Any, object()),
        cast(Any, storage),
    )
    result = await service.canonicalize(
        UUID(int=1),
        [binding.version.id for binding in bindings],
        max_source_bytes=10_000,
    )
    assert len(result.operations) == 1
    assert len(result.documentation_refs) == 20
    assert result.provenance.source_version_ids == [binding.version.id for binding in bindings]
    storage.get.assert_awaited_once()
