import hashlib
from uuid import UUID

from app.parsers.documentation import chunk_document, parse_document


def test_markdown_sections_and_chunk_ids_are_deterministic() -> None:
    source_id = UUID(int=20)
    document = parse_document(
        b"# Products\n\nOverview.\n\n## Lookup\n\nUse the product identifier.",
        detected_format="markdown",
        source_version_id=source_id,
        title=None,
    )
    assert document.title == "Products"
    assert document.sections[1].path == ["Products", "Lookup"]

    project_id = UUID(int=21)
    generation_id = UUID(int=22)
    source_hash = hashlib.sha256(b"source").hexdigest()
    first = chunk_document(
        document,
        project_id=project_id,
        generation_id=generation_id,
        source_content_sha256=source_hash,
        max_chars=500,
        overlap_chars=50,
    )
    second = chunk_document(
        document,
        project_id=project_id,
        generation_id=generation_id,
        source_content_sha256=source_hash,
        max_chars=500,
        overlap_chars=50,
    )
    assert first == second
    assert first[0].chunk_id.startswith("chunk_")


def test_html_omits_active_content() -> None:
    document = parse_document(
        b"<html><head><title>Docs</title><script>secret()</script></head>"
        b"<body><h1>Safe</h1><p>Visible text</p></body></html>",
        detected_format="html",
        source_version_id=UUID(int=23),
        title=None,
    )
    assert "Visible text" in document.text
    assert "secret" not in document.text
