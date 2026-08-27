from uuid import UUID

from app.core.exceptions import SourceParseError

from .csv_document import parse_csv
from .docx import parse_docx
from .html import parse_html
from .json_document import parse_json_document
from .markdown import parse_markdown
from .models import NormalizedDocument
from .pdf import parse_pdf
from .text import parse_text
from .xlsx import parse_xlsx


def parse_document(
    value: bytes,
    *,
    detected_format: str,
    source_version_id: UUID,
    title: str | None,
    pdf_max_pages: int = 500,
    max_text_chars: int = 5_000_000,
) -> NormalizedDocument:
    if detected_format == "json":
        return parse_json_document(
            value,
            source_version_id=source_version_id,
            title=title,
            max_text_chars=max_text_chars,
        )
    if detected_format == "markdown":
        return parse_markdown(
            value,
            source_version_id=source_version_id,
            title=title,
            max_text_chars=max_text_chars,
        )
    if detected_format == "text":
        return parse_text(
            value,
            source_version_id=source_version_id,
            title=title,
            max_text_chars=max_text_chars,
        )
    if detected_format == "csv":
        return parse_csv(
            value,
            source_version_id=source_version_id,
            title=title,
            max_text_chars=max_text_chars,
        )
    if detected_format == "html":
        return parse_html(
            value,
            source_version_id=source_version_id,
            title=title,
            max_text_chars=max_text_chars,
        )
    if detected_format == "xlsx":
        return parse_xlsx(
            value,
            source_version_id=source_version_id,
            title=title,
            max_text_chars=max_text_chars,
        )
    if detected_format == "docx":
        return parse_docx(
            value,
            source_version_id=source_version_id,
            title=title,
            max_text_chars=max_text_chars,
        )
    if detected_format == "pdf":
        return parse_pdf(
            value,
            source_version_id=source_version_id,
            title=title,
            max_pages=pdf_max_pages,
            max_text_chars=max_text_chars,
        )
    raise SourceParseError(f"Unsupported documentation format: {detected_format}")
