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
        fields = _operation_changes(
            current,
            current_operations[key],
            previous,
            previous_operations[key],
        )
        current_semantic = current_enrichment.operations.get(key) if current_enrichment else None
        previous_semantic = previous_enrichment.operations.get(key) if previous_enrichment else None
        if _semantic_serialized(current_semantic) != _semantic_serialized(previous_semantic):
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
    current_api: CanonicalApi,
    current: CanonicalOperation,
    previous_api: CanonicalApi,
    previous: CanonicalOperation,
) -> list[str]:
    fields: list[tuple[str, Any, Any]] = [
        ("method", current.method, previous.method),
        ("path", current.path_template, previous.path_template),
        (
            "server",
            _effective_server(current_api, current),
            _effective_server(previous_api, previous),
        ),
        ("parameters", current.parameters, previous.parameters),
        ("request_body", current.request_body, previous.request_body),
        ("responses", current.responses, previous.responses),
        (
            "security",
            _operation_security(current_api, current),
            _operation_security(previous_api, previous),
        ),
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
    return [
        name
        for name, left, right in fields
        if _semantic_serialized(left) != _semantic_serialized(right)
    ]


def _changed_mapping(current: dict[str, Any], previous: dict[str, Any]) -> list[str]:
    keys = set(current) | set(previous)
    return [
        key
        for key in sorted(keys)
        if _semantic_serialized(current.get(key)) != _semantic_serialized(previous.get(key))
    ]


def _changed_documents(current: CanonicalApi, previous: CanonicalApi) -> list[UUID]:
    current_hashes = {item.content_sha256 for item in current.documentation_refs}
    previous_hashes = {item.content_sha256 for item in previous.documentation_refs}
    changed_hashes = current_hashes ^ previous_hashes
    return sorted(
        {
            item.source_version_id
            for item in [*current.documentation_refs, *previous.documentation_refs]
            if item.content_sha256 in changed_hashes
        },
        key=str,
    )


def _effective_server(api: CanonicalApi, operation: CanonicalOperation) -> object:
    if operation.server_ref is None:
        return None
    servers = {server.key: server for server in api.servers}
    server = servers.get(operation.server_ref)
    if server is None:
        return {"missing_server_ref": operation.server_ref}
    return {"url": str(server.url)}


def _operation_security(api: CanonicalApi, operation: CanonicalOperation) -> object:
    referenced = {
        scheme for requirement in operation.security for scheme in requirement.scheme_scopes
    }
    return {
        "requirements": operation.security,
        "schemes": {
            key: api.security_schemes[key]
            for key in sorted(referenced)
            if key in api.security_schemes
        },
    }


def _semantic_serialized(value: Any) -> bytes:
    """Serialize executable values while excluding model-owned provenance fields.

    Traversing the Pydantic model structure is intentional: arbitrary JSON Schema
    objects may legitimately contain properties named ``source_ref`` or
    ``provenance`` and must not be rewritten.
    """

    return canonical_json_bytes(_semantic_jsonable(value))


def _semantic_jsonable(value: Any, serialized: Any = None) -> Any:
    if isinstance(value, BaseModel):
        dumped = value.model_dump(mode="json", by_alias=True)
        return {
            field.alias or name: _semantic_jsonable(
                getattr(value, name),
                dumped[field.alias or name],
            )
            for name, field in type(value).model_fields.items()
            if name not in {"source_ref", "provenance"}
        }
    if isinstance(value, dict):
        raw_mapping = cast(dict[object, object], value)
        dumped_mapping = cast(dict[str, Any], serialized) if isinstance(serialized, dict) else {}
        return {
            str(key): _semantic_jsonable(item, dumped_mapping.get(str(key)))
            for key, item in raw_mapping.items()
        }
    if isinstance(value, list):
        raw_items = cast(list[object], value)
        dumped_items = (
            cast(list[Any], serialized) if isinstance(serialized, list) else [None] * len(raw_items)
        )
        return [
            _semantic_jsonable(item, dumped_items[index]) for index, item in enumerate(raw_items)
        ]
    if isinstance(value, tuple):
        raw_items = cast(tuple[object, ...], value)
        dumped_items = (
            cast(list[Any], serialized) if isinstance(serialized, list) else [None] * len(raw_items)
        )
        return [
            _semantic_jsonable(item, dumped_items[index]) for index, item in enumerate(raw_items)
        ]
    return serialized if serialized is not None else _jsonable(value)


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
