import json
import math
from collections.abc import Hashable, Mapping
from typing import Any, cast

import yaml
from mcp_contracts.json_types import JsonObject, JsonValue
from yaml import YAMLError

from app.core.exceptions import SourceParseError

_MAX_NODES = 200_000
_MAX_DEPTH = 100
_MAX_ALIASES = 50


def _reject_duplicate_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SourceParseError(f"Duplicate object key is not allowed: {key!r}")
        result[key] = value
    return result


class _BoundedSafeLoader(yaml.SafeLoader):
    def __init__(self, stream: str) -> None:
        super().__init__(stream)
        self.alias_count = 0

    def compose_node(self, parent: yaml.Node | None, index: int) -> yaml.Node:
        if self._is_alias_event():
            self.alias_count += 1
            if self.alias_count > _MAX_ALIASES:
                raise SourceParseError("YAML contains too many aliases")
        node = super().compose_node(parent, index)
        if node is None:
            raise SourceParseError("YAML contains an incomplete node")
        return node

    def _is_alias_event(self) -> bool:
        return cast(
            bool,
            cast(
                object,
                self.check_event(  # pyright: ignore[reportUnknownMemberType]
                    yaml.AliasEvent
                ),
            ),
        )

    def _construct_value(self, node: yaml.Node, *, deep: bool) -> object:
        return cast(
            object,
            self.construct_object(node, deep=deep),  # pyright: ignore[reportUnknownMemberType]
        )

    def construct_mapping(
        self,
        node: yaml.MappingNode,
        deep: bool = False,
    ) -> dict[Hashable, Any]:
        self.flatten_mapping(node)
        result: dict[Hashable, Any] = {}
        for key_node, value_node in node.value:
            raw_key = self._construct_value(key_node, deep=deep)
            if not isinstance(raw_key, Hashable):
                raise SourceParseError("YAML object keys must be scalar")
            key = cast(Hashable, raw_key)
            try:
                duplicate = key in result
            except TypeError as exc:  # defensive for custom hashable objects
                raise SourceParseError("YAML object keys must be scalar") from exc
            if duplicate:
                raise SourceParseError(f"Duplicate YAML object key is not allowed: {key!r}")
            result[key] = self._construct_value(value_node, deep=deep)
        return result


def _validate_tree(root: object) -> None:
    stack: list[tuple[object, int, frozenset[int]]] = [(root, 0, frozenset())]
    nodes = 0
    while stack:
        value, depth, ancestors = stack.pop()
        nodes += 1
        if nodes > _MAX_NODES:
            raise SourceParseError("Structured source exceeds the node limit")
        if depth > _MAX_DEPTH:
            raise SourceParseError("Structured source exceeds the nesting limit")
        if isinstance(value, Mapping):
            container: Mapping[object, object] | list[object] = cast(Mapping[object, object], value)
            children = list(container.values())
        elif isinstance(value, list):
            container = cast(list[object], value)
            children = container
        else:
            continue
        identity = id(container)
        if identity in ancestors:
            raise SourceParseError("Structured source contains a recursive alias")
        nested_ancestors = ancestors | {identity}
        stack.extend((child, depth + 1, nested_ancestors) for child in children)


def _json_value(value: object, *, path: str = "$") -> JsonValue:
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SourceParseError(f"Structured source contains a non-finite number at {path}")
        return value
    if isinstance(value, Mapping):
        output: JsonObject = {}
        for raw_key, item in cast(Mapping[object, object], value).items():
            if not isinstance(raw_key, str):
                raise SourceParseError(f"Structured source object key at {path} must be text")
            output[raw_key] = _json_value(item, path=f"{path}/{raw_key}")
        return output
    if isinstance(value, list):
        return [
            _json_value(item, path=f"{path}/{index}")
            for index, item in enumerate(cast(list[object], value))
        ]
    raise SourceParseError(
        f"Structured source contains unsupported YAML value at {path}: {type(value).__name__}"
    )


def parse_json_or_yaml(value: bytes) -> tuple[str, JsonObject]:
    try:
        text = value.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceParseError("Executable source must be UTF-8 JSON or YAML") from exc
    try:
        parsed = cast(
            object,
            json.loads(text, object_pairs_hook=_reject_duplicate_json_pairs),
        )
        detected = "json"
    except json.JSONDecodeError:
        try:
            parsed = cast(object, yaml.load(text, Loader=_BoundedSafeLoader))
        except SourceParseError:
            raise
        except (YAMLError, RecursionError) as exc:
            mark = getattr(exc, "problem_mark", None)
            details: dict[str, object] = {}
            if mark is not None:
                details = {"line": mark.line + 1, "column": mark.column + 1}
            raise SourceParseError(
                "Executable source is not valid JSON or YAML",
                details=details,
            ) from exc
        detected = "yaml"
    except RecursionError as exc:
        raise SourceParseError("Structured source exceeds the nesting limit") from exc
    if not isinstance(parsed, Mapping):
        raise SourceParseError("Executable source root must be an object")
    parsed_mapping = cast(Mapping[object, object], parsed)
    _validate_tree(parsed_mapping)
    normalized = _json_value(parsed_mapping)
    if not isinstance(normalized, dict):
        raise SourceParseError("Executable source root must be an object")
    return detected, normalized
