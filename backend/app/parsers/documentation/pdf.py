from collections.abc import Mapping
from typing import Protocol, cast
from uuid import UUID

import pymupdf

from app.core.exceptions import SourceParseError

from .models import DocumentSection, NormalizedDocument


class _PdfPage(Protocol):
    def get_text(self, option: str, *, sort: bool) -> str: ...


class _PdfDocument(Protocol):
    needs_pass: bool
    page_count: int
    metadata: Mapping[str, object] | None

    def load_page(self, page_id: int) -> _PdfPage: ...

    def close(self) -> None: ...


def parse_pdf(
    value: bytes,
    *,
    source_version_id: UUID,
    title: str | None,
    max_pages: int,
    max_text_chars: int,
) -> NormalizedDocument:
    try:
        document = cast(
            _PdfDocument,
            cast(object, pymupdf.open(stream=value, filetype="pdf")),
        )
    except Exception as exc:
        raise SourceParseError("PDF documentation is invalid or unreadable") from exc
    try:
        if document.needs_pass:
            raise SourceParseError("Encrypted PDF documentation is not supported")
        if document.page_count > max_pages:
            raise SourceParseError("PDF documentation exceeds the configured page limit")
        metadata = document.metadata or {}
        raw_metadata_title = metadata.get("title")
        metadata_title = (
            raw_metadata_title.strip()
            if isinstance(raw_metadata_title, str) and raw_metadata_title.strip()
            else None
        )
        document_title = title or metadata_title
        sections: list[DocumentSection] = []
        total_chars = 0
        for index in range(document.page_count):
            page = document.load_page(index)
            text = page.get_text("text", sort=True).strip()
            if not text:
                continue
            total_chars += len(text)
            if total_chars > max_text_chars:
                raise SourceParseError("PDF extracted text exceeds the configured limit")
            sections.append(
                DocumentSection(
                    path=[document_title or "Document", f"Page {index + 1}"],
                    heading=f"Page {index + 1}",
                    text=text,
                    ordinal=len(sections),
                )
            )
        if not sections:
            raise SourceParseError(
                "PDF contains insufficient extractable text; image-only PDFs require OCR, "
                "which is outside V1"
            )
        return NormalizedDocument(
            source_version_id=source_version_id,
            title=document_title,
            text="\n\n".join(section.text for section in sections),
            sections=sections,
            metadata={"format": "pdf", "page_count": document.page_count},
        )
    finally:
        document.close()
