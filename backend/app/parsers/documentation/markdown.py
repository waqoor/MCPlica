from uuid import UUID

from markdown_it import MarkdownIt

from app.core.exceptions import SourceParseError

from .common import decode_utf8, ensure_text_limit
from .models import DocumentSection, NormalizedDocument


def parse_markdown(
    value: bytes,
    *,
    source_version_id: UUID,
    title: str | None,
    max_text_chars: int,
) -> NormalizedDocument:
    decoded = decode_utf8(value, label="Markdown", max_text_chars=max_text_chars)
    tokens = MarkdownIt("commonmark", {"html": False}).parse(decoded)
    headings: list[str] = []
    sections: list[DocumentSection] = []
    pending_heading_level: int | None = None
    pending_heading = False
    current_lines: list[str] = []

    def flush() -> None:
        text = "\n\n".join(line.strip() for line in current_lines if line.strip()).strip()
        current_lines.clear()
        if not text:
            return
        path = list(headings) or [title or "Document"]
        sections.append(
            DocumentSection(
                path=path,
                heading=headings[-1] if headings else title,
                text=text,
                ordinal=len(sections),
            )
        )

    for token in tokens:
        if token.type == "heading_open":
            flush()
            pending_heading_level = int(token.tag[1:])
            pending_heading = True
        elif token.type == "inline" and pending_heading:
            assert pending_heading_level is not None
            heading = token.content.strip()
            headings[:] = headings[: pending_heading_level - 1]
            headings.append(heading or f"Section {len(sections) + 1}")
            pending_heading = False
            pending_heading_level = None
        elif token.type in {"inline", "fence", "code_block"} and token.content.strip():
            current_lines.append(token.content)
    flush()
    if not sections:
        raise SourceParseError("Markdown documentation contains no extractable text")
    inferred_title = title
    if inferred_title is None and sections[0].heading:
        inferred_title = sections[0].path[0]
    full_text = "\n\n".join(
        "\n".join([*(section.path[-1:] if section.heading else []), section.text])
        for section in sections
    )
    ensure_text_limit(full_text, label="Markdown", max_text_chars=max_text_chars)
    return NormalizedDocument(
        source_version_id=source_version_id,
        title=inferred_title,
        text=full_text,
        sections=sections,
        metadata={"format": "markdown"},
    )
