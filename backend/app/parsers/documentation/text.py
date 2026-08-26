import re
from uuid import UUID

from app.core.exceptions import SourceParseError

from .models import DocumentSection, NormalizedDocument

_BLANK_LINES = re.compile(r"\n\s*\n+")


def parse_text(value: bytes, *, source_version_id: UUID, title: str | None) -> NormalizedDocument:
    try:
        decoded = value.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceParseError("Text documentation must be UTF-8") from exc
    normalized = decoded.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise SourceParseError("Documentation contains no text")
    blocks = [block.strip() for block in _BLANK_LINES.split(normalized) if block.strip()]
    root = title or "Document"
    sections = [
        DocumentSection(path=[root], heading=title, text=block, ordinal=index)
        for index, block in enumerate(blocks)
    ]
    return NormalizedDocument(
        source_version_id=source_version_id,
        title=title,
        text="\n\n".join(blocks),
        sections=sections,
        metadata={"format": "text"},
    )
