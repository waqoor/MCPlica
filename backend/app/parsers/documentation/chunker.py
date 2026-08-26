import hashlib
import re
from uuid import UUID

from .models import DocumentChunk, NormalizedDocument

_PARAGRAPHS = re.compile(r"\n\s*\n+")


def _bounded_segments(text: str, max_chars: int) -> list[str]:
    paragraphs = [item.strip() for item in _PARAGRAPHS.split(text) if item.strip()]
    result: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            result.append(current)
            current = ""
        remaining = paragraph
        while len(remaining) > max_chars:
            boundary = remaining.rfind(" ", 0, max_chars + 1)
            if boundary < max_chars // 2:
                boundary = max_chars
            result.append(remaining[:boundary].strip())
            remaining = remaining[boundary:].strip()
        current = remaining
    if current:
        result.append(current)
    return result


def chunk_document(
    document: NormalizedDocument,
    *,
    project_id: UUID,
    generation_id: UUID,
    source_content_sha256: str,
    max_chars: int,
    overlap_chars: int,
) -> list[DocumentChunk]:
    if max_chars < 100 or overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("Chunk size must be positive and overlap smaller than the chunk")
    chunks: list[DocumentChunk] = []
    ordinal = 0
    for section in document.sections:
        previous = ""
        for segment in _bounded_segments(section.text, max_chars):
            available_overlap = max(0, max_chars - len(segment) - 2)
            overlap_size = min(overlap_chars, available_overlap)
            overlap = previous[-overlap_size:].strip() if previous and overlap_size else ""
            chunk_text = f"{overlap}\n\n{segment}".strip() if overlap else segment
            content_digest = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
            identity = "\x00".join(
                [
                    source_content_sha256,
                    "/".join(item.strip().casefold() for item in section.path),
                    str(ordinal),
                    content_digest,
                ]
            )
            chunk_id = f"chunk_{hashlib.sha256(identity.encode()).hexdigest()}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    project_id=project_id,
                    generation_id=generation_id,
                    source_version_id=document.source_version_id,
                    title=document.title,
                    section_path=section.path,
                    text=chunk_text,
                    content_sha256=content_digest,
                )
            )
            ordinal += 1
            previous = segment
    return chunks
