import re
from uuid import UUID

from app.core.exceptions import SourceParseError

from .common import decode_utf8
from .models import DocumentSection, NormalizedDocument

_BLANK_LINES = re.compile(r"\n\s*\n+")


def parse_text(
    value: bytes,
    *,
    source_version_id: UUID,
    title: str | None,
    max_text_chars: int,
) -> NormalizedDocument:
    decoded = decode_utf8(value, label="Text", max_text_chars=max_text_chars)
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
