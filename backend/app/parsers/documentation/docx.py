import re
from io import BytesIO
from uuid import UUID

from docx import Document

from app.core.exceptions import SourceParseError

from .common import ensure_text_limit
from .models import DocumentSection, NormalizedDocument
from .office import detect_office_document_format

_HEADING = re.compile(r"^heading\s+([1-6])$", re.IGNORECASE)
_MAX_DOCX_BLOCKS = 200_000
_MAX_DOCX_TABLE_CELLS = 2_000_000


def parse_docx(
    value: bytes,
    *,
    source_version_id: UUID,
    title: str | None,
    max_text_chars: int,
) -> NormalizedDocument:
    if detect_office_document_format(value) != "docx":
        raise SourceParseError("Office document is not a DOCX document")
    try:
        document = Document(BytesIO(value))
    except Exception as exc:
        raise SourceParseError("DOCX documentation is invalid or unreadable") from exc

    metadata_title = (document.core_properties.title or "").strip() or None
    document_title = title or metadata_title
    root = document_title or "Document"
    headings: list[str] = []
    current_lines: list[str] = []
    sections: list[DocumentSection] = []
    total_chars = 0
    block_count = 0
    table_cells = 0

    def add_text(text: str) -> None:
        nonlocal total_chars
        total_chars += len(text) + 1
        if total_chars > max_text_chars:
            raise SourceParseError("DOCX extracted text exceeds the configured limit")

    def flush() -> None:
        text = "\n\n".join(current_lines).strip()
        current_lines.clear()
        if not text:
            return
        sections.append(
            DocumentSection(
                path=list(headings) or [root],
                heading=headings[-1] if headings else document_title,
                text=text,
                ordinal=len(sections),
            )
        )

    for paragraph in document.paragraphs:
        block_count += 1
        if block_count > _MAX_DOCX_BLOCKS:
            raise SourceParseError("DOCX documentation exceeds the block limit")
        text = paragraph.text.strip()
        if not text:
            continue
        style = paragraph.style
        style_name = (style.name or "") if style is not None else ""
        heading_match = _HEADING.fullmatch(style_name.strip())
        if heading_match:
            flush()
            level = int(heading_match.group(1))
            headings[:] = headings[: level - 1]
            headings.append(text)
            add_text(text)
        else:
            add_text(text)
            current_lines.append(text)
    flush()

    for table_number, table in enumerate(document.tables, start=1):
        block_count += 1
        if block_count > _MAX_DOCX_BLOCKS:
            raise SourceParseError("DOCX documentation exceeds the block limit")
        lines: list[str] = []
        for row in table.rows:
            table_cells += len(row.cells)
            if table_cells > _MAX_DOCX_TABLE_CELLS:
                raise SourceParseError("DOCX documentation exceeds the table cell limit")
            rendered = [cell.text.strip().replace("\n", "\\n") for cell in row.cells]
            while rendered and not rendered[-1]:
                rendered.pop()
            if rendered:
                line = "\t".join(rendered)
                add_text(line)
                lines.append(line)
        if lines:
            heading = f"Table {table_number}"
            sections.append(
                DocumentSection(
                    path=[root, heading],
                    heading=heading,
                    text="\n".join(lines),
                    ordinal=len(sections),
                )
            )
    if not sections:
        raise SourceParseError("DOCX documentation contains no extractable text")
    if document_title is None and sections[0].heading:
        document_title = sections[0].path[0]
    text = "\n\n".join(
        "\n".join([*(section.path[-1:] if section.heading else []), section.text])
        for section in sections
    )
    ensure_text_limit(text, label="DOCX", max_text_chars=max_text_chars)
    return NormalizedDocument(
        source_version_id=source_version_id,
        title=document_title,
        text=text,
        sections=sections,
        metadata={
            "format": "docx",
            "paragraph_count": len(document.paragraphs),
            "table_count": len(document.tables),
        },
    )
