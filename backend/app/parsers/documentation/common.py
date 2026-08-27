from app.core.exceptions import SourceParseError


def decode_utf8(value: bytes, *, label: str, max_text_chars: int) -> str:
    try:
        decoded = value.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceParseError(f"{label} documentation must be UTF-8") from exc
    ensure_text_limit(decoded, label=label, max_text_chars=max_text_chars)
    return decoded


def ensure_text_limit(text: str, *, label: str, max_text_chars: int) -> None:
    if len(text) > max_text_chars:
        raise SourceParseError(f"{label} extracted text exceeds the configured limit")
