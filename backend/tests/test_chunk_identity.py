import hashlib
from uuid import UUID

import pytest

from app.parsers.documentation import DocumentSection, NormalizedDocument, chunk_document


def _chunks(project: int = 1, generation: int = 2, source: int = 3):
    text = "The same API documentation can be attached to multiple projects and builds."
    document = NormalizedDocument(
        source_version_id=UUID(int=source),
        title="Guide",
        text=text,
        sections=[DocumentSection(path=["Guide"], text=text, ordinal=0)],
    )
    return chunk_document(
        document,
        project_id=UUID(int=project),
        generation_id=UUID(int=generation),
        source_content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        max_chars=500,
        overlap_chars=0,
    )


@pytest.mark.parametrize("changed", [{"project": 4}, {"generation": 4}, {"source": 4}])
def test_chunk_row_identity_includes_every_storage_scope(changed: dict[str, int]) -> None:
    original = _chunks()[0]
    other = _chunks(**changed)[0]
    assert original.chunk_id != other.chunk_id
    assert original.content_sha256 == other.content_sha256
    assert original.text == other.text


def test_repeated_upsert_is_idempotent_without_overwriting_other_scopes() -> None:
    scopes = [_chunks()[0], _chunks(project=4)[0], _chunks(generation=4)[0], _chunks(source=4)[0]]
    rows = {chunk.chunk_id: chunk for chunk in scopes}
    rows.update({chunk.chunk_id: chunk for chunk in _chunks()})
    assert len(rows) == 4
    assert _chunks() == _chunks()
    remaining = {
        key: chunk
        for key, chunk in rows.items()
        if not (chunk.project_id == UUID(int=1) and chunk.generation_id == UUID(int=2))
    }
    assert set(remaining) == {scopes[1].chunk_id, scopes[2].chunk_id}
