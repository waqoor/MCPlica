import json
import math
from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID

from app.core.exceptions import SourceParseError

from .common import decode_utf8, ensure_text_limit
from .models import DocumentSection, NormalizedDocument

_MAX_JSON_DEPTH = 100
_MAX_JSON_NODES = 500_000


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise SourceParseError(f"Duplicate JSON object key is not allowed: {key!r}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise SourceParseError(f"JSON documentation contains an invalid number: {value}")


def _validate_tree(root: object) -> None:
    nodes = 0
    stack: list[tuple[object, int]] = [(root, 0)]
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > _MAX_JSON_NODES:
            raise SourceParseError("JSON documentation exceeds the node limit")
        if depth > _MAX_JSON_DEPTH:
            raise SourceParseError("JSON documentation exceeds the nesting limit")
        if isinstance(value, Mapping):
            mapping = cast(Mapping[object, object], value)
            stack.extend((item, depth + 1) for item in mapping.values())
        elif isinstance(value, list):
            items = cast(list[object], value)
            stack.extend((item, depth + 1) for item in items)
        elif isinstance(value, float) and not math.isfinite(value):
            raise SourceParseError("JSON documentation contains a non-finite number")


def parse_json_document(
    value: bytes,
    *,
    source_version_id: UUID,
    title: str | None,
    max_text_chars: int,
) -> NormalizedDocument:
    decoded = decode_utf8(value, label="JSON", max_text_chars=max_text_chars)
    try:
        parsed = cast(
            object,
            json.loads(
                decoded,
                object_pairs_hook=_object_without_duplicates,
                parse_constant=_invalid_constant,
            ),
        )
    except SourceParseError:
        raise
    except (TypeError, ValueError, RecursionError) as exc:
        raise SourceParseError("JSON documentation is invalid") from exc
    _validate_tree(parsed)
    text = json.dumps(
        cast(Any, parsed),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    ensure_text_limit(text, label="JSON", max_text_chars=max_text_chars)
    root = title or "JSON document"
    return NormalizedDocument(
        source_version_id=source_version_id,
        title=title,
        text=text,
        sections=[DocumentSection(path=[root], heading=title, text=text, ordinal=0)],
        metadata={"format": "json"},
    )
