import csv
from io import StringIO
from uuid import UUID

from app.core.exceptions import SourceParseError

from .common import decode_utf8, ensure_text_limit
from .models import DocumentSection, NormalizedDocument

_MAX_CSV_ROWS = 200_000
_MAX_CSV_CELLS = 2_000_000


def _cell_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n").replace("\t", "\\t")


def parse_csv(
    value: bytes,
    *,
    source_version_id: UUID,
    title: str | None,
    max_text_chars: int,
) -> NormalizedDocument:
    decoded = decode_utf8(value, label="CSV", max_text_chars=max_text_chars)
    lines: list[str] = []
    cell_count = 0
    try:
        for row_number, row in enumerate(csv.reader(StringIO(decoded, newline="")), start=1):
            if row_number > _MAX_CSV_ROWS:
                raise SourceParseError("CSV documentation exceeds the row limit")
            cell_count += len(row)
            if cell_count > _MAX_CSV_CELLS:
                raise SourceParseError("CSV documentation exceeds the cell limit")
            rendered = [_cell_text(cell.strip()) for cell in row]
            while rendered and not rendered[-1]:
                rendered.pop()
            if rendered:
                lines.append("\t".join(rendered))
    except csv.Error as exc:
        raise SourceParseError("CSV documentation is invalid") from exc
    if not lines:
        raise SourceParseError("CSV documentation contains no text")
    text = "\n".join(lines)
    ensure_text_limit(text, label="CSV", max_text_chars=max_text_chars)
    root = title or "CSV document"
    return NormalizedDocument(
        source_version_id=source_version_id,
        title=title,
        text=text,
        sections=[DocumentSection(path=[root], heading=title, text=text, ordinal=0)],
        metadata={"format": "csv", "row_count": len(lines)},
    )
