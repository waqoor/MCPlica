from uuid import UUID

from bs4 import BeautifulSoup

from app.core.exceptions import SourceParseError

from .common import decode_utf8, ensure_text_limit
from .models import DocumentSection, NormalizedDocument

_CONTENT_TAGS = {"p", "li", "pre", "blockquote", "dt", "dd", "td", "th"}


def parse_html(
    value: bytes,
    *,
    source_version_id: UUID,
    title: str | None,
    max_text_chars: int,
) -> NormalizedDocument:
    decoded = decode_utf8(value, label="HTML", max_text_chars=max_text_chars)
    soup = BeautifulSoup(decoded, "html.parser")
    for element in soup(["script", "style", "noscript", "iframe", "object", "template"]):
        element.decompose()
    document_title = title
    if document_title is None and soup.title:
        document_title = soup.title.get_text(" ", strip=True) or None
    headings: list[str] = []
    current_lines: list[str] = []
    sections: list[DocumentSection] = []

    def flush() -> None:
        text = "\n".join(dict.fromkeys(line for line in current_lines if line)).strip()
        current_lines.clear()
        if text:
            sections.append(
                DocumentSection(
                    path=list(headings) or [document_title or "Document"],
                    heading=headings[-1] if headings else document_title,
                    text=text,
                    ordinal=len(sections),
                )
            )

    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", *_CONTENT_TAGS]):
        if element.name and element.name.startswith("h"):
            flush()
            level = int(element.name[1:])
            heading = element.get_text(" ", strip=True)
            if heading:
                headings[:] = headings[: level - 1]
                headings.append(heading)
        elif element.name in _CONTENT_TAGS:
            if element.find_parent(_CONTENT_TAGS):
                continue
            text = element.get_text(" ", strip=True)
            if text:
                current_lines.append(text)
    flush()
    if not sections:
        fallback = soup.get_text(" ", strip=True)
        if not fallback:
            raise SourceParseError("HTML documentation contains no extractable text")
        sections.append(
            DocumentSection(
                path=[document_title or "Document"],
                heading=document_title,
                text=fallback,
                ordinal=0,
            )
        )
    text = "\n\n".join(section.text for section in sections)
    ensure_text_limit(text, label="HTML", max_text_chars=max_text_chars)
    return NormalizedDocument(
        source_version_id=source_version_id,
        title=document_title,
        text=text,
        sections=sections,
        metadata={"format": "html"},
    )
