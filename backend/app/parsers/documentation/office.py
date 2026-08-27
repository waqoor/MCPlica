from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, LargeZipFile, ZipFile

from app.core.exceptions import SourceParseError

_MAX_ARCHIVE_ENTRIES = 10_000
_MAX_ARCHIVE_UNCOMPRESSED_BYTES = 250_000_000
_MAX_COMPRESSION_RATIO = 1_000
_MIN_RATIO_CHECK_BYTES = 1_000_000


def detect_office_document_format(value: bytes) -> str:
    try:
        with ZipFile(BytesIO(value)) as archive:
            entries = archive.infolist()
            if len(entries) > _MAX_ARCHIVE_ENTRIES:
                raise SourceParseError("Office document contains too many archive entries")
            names: set[str] = set()
            total_uncompressed = 0
            for entry in entries:
                normalized = entry.filename.replace("\\", "/")
                path = PurePosixPath(normalized)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or (path.parts and ":" in path.parts[0])
                ):
                    raise SourceParseError("Office document contains an unsafe archive path")
                if entry.flag_bits & 0x1:
                    raise SourceParseError("Encrypted Office documents are not supported")
                if entry.is_dir():
                    continue
                names.add(normalized.casefold())
                total_uncompressed += entry.file_size
                if total_uncompressed > _MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise SourceParseError(
                        "Office document expands beyond the configured safety limit"
                    )
                if entry.file_size >= _MIN_RATIO_CHECK_BYTES:
                    if entry.compress_size == 0:
                        raise SourceParseError("Office document contains an invalid archive entry")
                    if entry.file_size / entry.compress_size > _MAX_COMPRESSION_RATIO:
                        raise SourceParseError(
                            "Office document contains a suspiciously compressed archive entry"
                        )
    except (BadZipFile, LargeZipFile, OSError) as exc:
        raise SourceParseError("Office document is not a valid XLSX or DOCX package") from exc

    if any(name.endswith("vbaproject.bin") for name in names):
        raise SourceParseError("Macro-enabled Office documents are not supported")
    is_xlsx = "xl/workbook.xml" in names
    is_docx = "word/document.xml" in names
    if is_xlsx == is_docx:
        raise SourceParseError("Office document is not a valid XLSX or DOCX package")
    return "xlsx" if is_xlsx else "docx"
