import re
from collections import Counter
from collections.abc import Mapping
from typing import cast
from urllib.parse import unquote, urlsplit

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from .manifest import MCPManifest, ParameterTarget
from .path_template import path_parameter_names

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_ENCODED_SEPARATOR = re.compile(r"%(?:2f|5c)", re.IGNORECASE)
_FORBIDDEN_CALLER_HEADERS = {
    "authorization",
    "connection",
    "content-length",
    "content-type",
    "cookie",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "set-cookie",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def validate_operation_path(path: str) -> None:
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("manifest operation paths must be origin-relative")
    if _CONTROL_CHARACTERS.search(path) or "\\" in path:
        raise ValueError("manifest operation path contains forbidden characters")
    if "?" in path or "#" in path:
        raise ValueError("manifest operation path cannot contain query or fragment data")
    if _ENCODED_SEPARATOR.search(path):
        raise ValueError("manifest operation path cannot contain encoded path separators")
    decoded = unquote(path)
    if any(segment in {".", ".."} for segment in decoded.split("/")):
        raise ValueError("manifest operation path cannot contain dot segments")


def validate_runtime_compatibility(specifier: str, runtime_version: str) -> None:
    try:
        compatible = Version(runtime_version) in SpecifierSet(specifier)
    except (InvalidSpecifier, InvalidVersion) as exc:
        raise ValueError("manifest runtime compatibility range is invalid") from exc
    if not compatible:
        raise ValueError("manifest is incompatible with this runtime version")


def _normalize_allowed_host(value: str) -> str:
    if "://" in value or any(character in value for character in "/?#@\\\r\n\x00"):
        raise ValueError("manifest allowed upstream hosts must contain host names only")
    parsed = urlsplit(f"//{value}")
    if not parsed.hostname:
        raise ValueError("manifest contains an invalid allowed upstream host")
    try:
        if parsed.port is not None:
            raise ValueError("manifest allowed upstream hosts cannot contain ports")
        return parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError) as exc:
        raise ValueError("manifest contains an invalid allowed upstream host") from exc


def _validate_local_schema_references(schema: Mapping[str, object], *, label: str) -> None:
    root = schema
    pending: list[object] = [schema]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            mapping = cast(dict[str, object], value)
            reference = mapping.get("$ref")
            if reference is not None:
                if not isinstance(reference, str) or not reference.startswith("#"):
                    raise ValueError(f"{label} contains a non-local JSON Schema reference")
                _resolve_local_schema_reference(root, reference, label=label)
            pending.extend(mapping.values())
        elif isinstance(value, list):
            pending.extend(cast(list[object], value))


def _resolve_local_schema_reference(
    root: Mapping[str, object],
    reference: str,
    *,
    label: str,
) -> None:
    if reference == "#":
        return
    if not reference.startswith("#/"):
        raise ValueError(f"{label} contains an unsupported local JSON Schema anchor")
    current: object = root
    for raw_token in reference[2:].split("/"):
        token = unquote(raw_token).replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = cast(dict[str, object], current)[token]
            continue
        if isinstance(current, list) and token.isdigit():
            index = int(token)
            sequence = cast(list[object], current)
            if index < len(sequence):
                current = sequence[index]
                continue
        raise ValueError(f"{label} contains an unresolved local JSON Schema reference")


def validate_manifest_contract(manifest: MCPManifest, *, runtime_version: str) -> None:
    """Validate every infrastructure-independent invariant used by the generic runtime."""

    validate_runtime_compatibility(manifest.runtime_compatibility, runtime_version)

    server_ids = [server.id for server in manifest.servers]
    auth_ids = [profile.id for profile in manifest.auth_profiles]
    tool_names = [tool.name for tool in manifest.tools]
    resource_uris = [resource.uri for resource in manifest.resources]
    for label, values in (
        ("server ids", server_ids),
        ("auth profile ids", auth_ids),
        ("tool names", tool_names),
        ("resource URIs", resource_uris),
    ):
        duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
        if duplicates:
            raise ValueError(f"manifest contains duplicate {label}: {duplicates}")

    known_servers = set(server_ids)
    known_auth = set(auth_ids)
    server_hosts: set[str] = set()
    for server in manifest.servers:
        parsed = urlsplit(str(server.url))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"server {server.id!r} has an invalid HTTP URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(f"server {server.id!r} URL contains forbidden components")
        server_hosts.add(parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower())

    allowed_hosts = {
        _normalize_allowed_host(host) for host in manifest.security.allowed_upstream_hosts
    }
    if allowed_hosts != server_hosts:
        raise ValueError("manifest upstream host allowlist must match configured API servers")

    for tool in manifest.tools:
        mapping = tool.request_mapping
        if mapping.server_ref not in known_servers:
            raise ValueError(f"tool {tool.name!r} references an unknown server")
        if tool.security_profile_ref and tool.security_profile_ref not in known_auth:
            raise ValueError(f"tool {tool.name!r} references an unknown auth profile")
        if tool.input_schema.get("type") != "object":
            raise ValueError(f"tool {tool.name!r} input schema must be object-shaped")
        if tool.output_schema is not None and tool.output_schema.get("type") != "object":
            raise ValueError(f"tool {tool.name!r} output schema must be object-shaped")
        _validate_local_schema_references(
            tool.input_schema, label=f"tool {tool.name!r} input schema"
        )
        if tool.output_schema is not None:
            _validate_local_schema_references(
                tool.output_schema, label=f"tool {tool.name!r} output schema"
            )
        for response in tool.responses:
            if response.schema_ is not None:
                _validate_local_schema_references(
                    response.schema_,
                    label=f"tool {tool.name!r} response schema",
                )
        validate_operation_path(mapping.path)

        mapped_fields = [parameter.tool_field for parameter in mapping.parameters]
        if mapping.body is not None:
            mapped_fields.append(mapping.body.tool_field)
        duplicate_fields = [value for value, count in Counter(mapped_fields).items() if count > 1]
        if duplicate_fields:
            raise ValueError(f"tool {tool.name!r} maps fields more than once: {duplicate_fields}")
        destinations = [
            (parameter.target, parameter.source_name.lower()) for parameter in mapping.parameters
        ]
        duplicate_destinations = [
            f"{target.value}:{name}"
            for (target, name), count in Counter(destinations).items()
            if count > 1
        ]
        if duplicate_destinations:
            raise ValueError(
                f"tool {tool.name!r} maps destinations more than once: {duplicate_destinations}"
            )

        raw_properties = tool.input_schema.get("properties", {})
        if not isinstance(raw_properties, dict):
            raise ValueError(f"tool {tool.name!r} schema properties must be an object")
        properties = cast(dict[str, object], raw_properties)
        unmapped = sorted(set(properties) - set(mapped_fields))
        if unmapped:
            raise ValueError(f"tool {tool.name!r} has unmapped input fields: {unmapped}")

        for parameter in mapping.parameters:
            if parameter.tool_field not in properties:
                raise ValueError(
                    f"tool {tool.name!r} maps absent schema field {parameter.tool_field!r}"
                )
            if parameter.target == ParameterTarget.PATH:
                placeholder = "{" + parameter.source_name + "}"
                if placeholder not in mapping.path:
                    raise ValueError(f"tool {tool.name!r} path is missing {placeholder}")
            if (
                parameter.target == ParameterTarget.HEADER
                and parameter.source_name.lower() in _FORBIDDEN_CALLER_HEADERS
            ):
                raise ValueError(f"tool {tool.name!r} maps a forbidden caller header")
            style = parameter.style
            if parameter.target == ParameterTarget.PATH and style not in {None, "simple"}:
                raise ValueError(f"tool {tool.name!r} has unsupported path serialization")
            if parameter.target == ParameterTarget.HEADER and style not in {None, "simple"}:
                raise ValueError(f"tool {tool.name!r} has unsupported header serialization")
            if parameter.target != ParameterTarget.QUERY and parameter.allow_reserved:
                raise ValueError("allow_reserved is valid only for query parameters")

        unresolved = path_parameter_names(mapping.path)
        declared_path = {
            parameter.source_name
            for parameter in mapping.parameters
            if parameter.target == ParameterTarget.PATH
        }
        if set(unresolved) != declared_path:
            raise ValueError(f"tool {tool.name!r} path placeholders do not match mappings")

        if mapping.body is not None and mapping.body.tool_field not in properties:
            raise ValueError(
                f"tool {tool.name!r} maps absent body field {mapping.body.tool_field!r}"
            )
        if mapping.body is not None:
            content_fields = [item.content_field for item in mapping.body.multipart_files]
            if len(content_fields) != len(set(content_fields)):
                raise ValueError(f"tool {tool.name!r} has duplicate multipart file mappings")
