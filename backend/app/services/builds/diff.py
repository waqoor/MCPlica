from typing import Any, cast
from uuid import UUID

from mcp_contracts import CanonicalApi, CanonicalOperation
from pydantic import BaseModel

from app.core.canonical_json import canonical_json_bytes
from app.domain.analysis import EnrichmentSnapshot
from app.domain.builds import BuildDiff, OperationChange


def diff_builds(
    current: CanonicalApi,
    previous: CanonicalApi | None,
    *,
    current_enrichment: EnrichmentSnapshot | None = None,
    previous_enrichment: EnrichmentSnapshot | None = None,
) -> BuildDiff:
    current_operations = {item.key: item for item in current.operations}
    if previous is None:
        return BuildDiff(
            added_operations=sorted(current_operations),
            changed_schemas=sorted(current.schemas),
            changed_security=sorted(current.security_schemes),
            changed_documents=sorted(
                (item.source_version_id for item in current.documentation_refs),
                key=str,
            ),
        )
    previous_operations = {item.key: item for item in previous.operations}
    current_keys = set(current_operations)
    previous_keys = set(previous_operations)
    changed: list[OperationChange] = []
    unchanged: list[str] = []
    for key in sorted(current_keys & previous_keys):
        fields = _operation_changes(current_operations[key], previous_operations[key])
        current_semantic = current_enrichment.operations.get(key) if current_enrichment else None
        previous_semantic = previous_enrichment.operations.get(key) if previous_enrichment else None
        if _serialized(current_semantic) != _serialized(previous_semantic):
            fields.append("semantic_enrichment")
        if fields:
            changed.append(OperationChange(operation_key=key, changes=fields))
        else:
            unchanged.append(key)
    return BuildDiff(
        added_operations=sorted(current_keys - previous_keys),
        removed_operations=sorted(previous_keys - current_keys),
        changed_operations=changed,
        unchanged_operations=unchanged,
        changed_schemas=_changed_mapping(current.schemas, previous.schemas),
        changed_security=_changed_mapping(
            current.security_schemes,
            previous.security_schemes,
        ),
        changed_documents=_changed_documents(current, previous),
    )


def _operation_changes(
    current: CanonicalOperation,
    previous: CanonicalOperation,
) -> list[str]:
    fields: list[tuple[str, Any, Any]] = [
        ("method", current.method, previous.method),
        ("path", current.path_template, previous.path_template),
        ("server", current.server_ref, previous.server_ref),
        ("parameters", current.parameters, previous.parameters),
        ("request_body", current.request_body, previous.request_body),
        ("responses", current.responses, previous.responses),
        ("security", current.security, previous.security),
        (
            "source_semantics",
            (current.summary, current.description, current.tags),
            (
                previous.summary,
                previous.description,
                previous.tags,
            ),
        ),
    ]
    return [name for name, left, right in fields if _serialized(left) != _serialized(right)]


def _changed_mapping(current: dict[str, Any], previous: dict[str, Any]) -> list[str]:
    keys = set(current) | set(previous)
    return [
        key
        for key in sorted(keys)
        if _serialized(current.get(key)) != _serialized(previous.get(key))
    ]


def _changed_documents(current: CanonicalApi, previous: CanonicalApi) -> list[UUID]:
    current_docs = {
        (item.source_version_id, item.content_sha256) for item in current.documentation_refs
    }
    previous_docs = {
        (item.source_version_id, item.content_sha256) for item in previous.documentation_refs
    }
    return sorted(
        {item[0] for item in current_docs ^ previous_docs},
        key=str,
    )


def _serialized(value: Any) -> bytes:
    return canonical_json_bytes(_jsonable(value))


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, dict):
        raw_mapping = cast(dict[object, object], value)
        return {str(key): _jsonable(item) for key, item in raw_mapping.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in cast(list[object], value)]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in cast(tuple[object, ...], value)]
    return value
