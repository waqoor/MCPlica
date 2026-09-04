import hashlib
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from datetime import datetime
from typing import Literal, cast
from urllib.parse import urlsplit

from mcp_contracts import (
    RUNTIME_COMPATIBILITY,
    VERSION,
    AuthProfile,
    BuildMetadata,
    CanonicalApi,
    CanonicalMediaType,
    CanonicalOperation,
    CanonicalSecurityScheme,
    ManifestProject,
    MCPManifest,
    MCPResource,
    MCPTool,
    MultipartFileMapping,
    ParameterMapping,
    RequestBodyMapping,
    RequestMapping,
    ResponseDefinition,
    RuntimeSecurity,
    SecuritySchemeType,
    ServerDefinition,
)
from mcp_contracts.canonical import ParameterLocation
from mcp_contracts.json_types import JsonObject, JsonValue
from mcp_contracts.manifest import ParameterTarget

from app.core.canonical_json import canonical_json_bytes, canonical_sha256
from app.core.exceptions import CompilationError
from app.domain.builds import BuildSecuritySelection

COMPILER_VERSION = VERSION
type SupportedMediaType = Literal[
    "application/json",
    "application/x-www-form-urlencoded",
    "multipart/form-data",
]
_SUPPORTED_MEDIA_TYPES: tuple[SupportedMediaType, ...] = (
    "application/json",
    "application/x-www-form-urlencoded",
    "multipart/form-data",
)
_FORBIDDEN_CALLER_HEADERS = {
    "authorization",
    "connection",
    "content-length",
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


def _compile_error(operation: CanonicalOperation, message: str) -> CompilationError:
    return CompilationError(
        f"{operation.method.value} {operation.path_template}: {message}",
        details={
            "operation_key": operation.key,
            "source_pointer": operation.provenance.operation.pointer,
        },
    )


def _profile(
    name: str,
    scheme: CanonicalSecurityScheme,
    selection: BuildSecuritySelection,
) -> AuthProfile:
    profile_identity = canonical_json_bytes(
        {
            "scheme": name,
            "credential_ref": selection.credential_ref,
            "scopes": selection.scopes,
            "token_auth_method": selection.token_auth_method,
        }
    )
    profile_id = f"auth_{hashlib.sha256(profile_identity).hexdigest()[:16]}"
    if scheme.type is SecuritySchemeType.HTTP_BEARER:
        return AuthProfile(id=profile_id, type="bearer", credential_ref=selection.credential_ref)
    if scheme.type is SecuritySchemeType.HTTP_BASIC:
        return AuthProfile(id=profile_id, type="basic", credential_ref=selection.credential_ref)
    if scheme.type is SecuritySchemeType.API_KEY:
        if scheme.location not in {"header", "query"} or not scheme.name:
            raise CompilationError(f"Security scheme {name!r} is not executable")
        return AuthProfile(
            id=profile_id,
            type="api_key",
            credential_ref=selection.credential_ref,
            location=cast(Literal["header", "query"], scheme.location),
            name=scheme.name,
        )
    if scheme.type is SecuritySchemeType.OAUTH2_CLIENT_CREDENTIALS:
        if scheme.token_url is None:
            raise CompilationError(f"Security scheme {name!r} has no token URL")
        return AuthProfile(
            id=profile_id,
            type="oauth2_client_credentials",
            credential_ref=selection.credential_ref,
            token_url=scheme.token_url,
            scopes=selection.scopes,
            token_auth_method=selection.token_auth_method,
        )
    if scheme.type is SecuritySchemeType.STATIC_HEADERS:
        if not scheme.name:
            raise CompilationError(f"Security scheme {name!r} has no header name")
        return AuthProfile(
            id=profile_id,
            type="static_header",
            credential_ref=selection.credential_ref,
            name=scheme.name,
        )
    raise CompilationError(f"Security scheme {name!r} is unsupported")


def _auth_profiles(
    api: CanonicalApi,
    security_selections: Mapping[str, BuildSecuritySelection],
    operations: Iterable[CanonicalOperation],
) -> tuple[list[AuthProfile], dict[str, str]]:
    profiles_by_id: dict[str, AuthProfile] = {}
    profile_refs: dict[str, str] = {}
    for operation in sorted(operations, key=lambda item: item.key):
        anonymous_allowed = not operation.security or any(
            not requirement.scheme_scopes for requirement in operation.security
        )
        selection = security_selections.get(operation.key)
        if selection is None:
            if anonymous_allowed:
                continue
            raise _compile_error(operation, "security alternative is unresolved")
        if anonymous_allowed:
            raise _compile_error(operation, "anonymous operation has an unnecessary credential")
        name = selection.scheme_name
        matching_requirements = [
            requirement
            for requirement in operation.security
            if len(requirement.scheme_scopes) == 1 and name in requirement.scheme_scopes
        ]
        if not matching_requirements:
            raise _compile_error(operation, "security selection is not a declared alternative")
        required_scopes = matching_requirements[0].scheme_scopes[name]
        if required_scopes and sorted(set(required_scopes)) != selection.scopes:
            raise _compile_error(operation, "OAuth security selection changed required scopes")
        scheme = api.security_schemes.get(name)
        if scheme is None:
            raise CompilationError(f"Security scheme {name!r} is not defined")
        profile = _profile(name, scheme, selection)
        profiles_by_id.setdefault(profile.id, profile)
        profile_refs[operation.key] = profile.id
    return [profiles_by_id[key] for key in sorted(profiles_by_id)], profile_refs


def _operation_auth_ref(
    operation: CanonicalOperation,
    profile_refs: Mapping[str, str],
) -> str | None:
    return profile_refs.get(operation.key)


def _unique_field_name(
    name: str,
    location: ParameterLocation,
    used: set[str],
) -> str:
    candidate = name
    if candidate in used:
        candidate = f"{location.value}_{name}"
    suffix = 2
    base = candidate
    while candidate in used:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _multipart_files(media: CanonicalMediaType) -> list[MultipartFileMapping]:
    properties = media.schema_.get("properties")
    required = media.schema_.get("required", [])
    if not isinstance(properties, dict):
        return []
    required_names = (
        {item for item in required if isinstance(item, str)}
        if isinstance(required, list)
        else set[str]()
    )
    result: list[MultipartFileMapping] = []
    for name, raw_schema in sorted(properties.items()):
        if not isinstance(raw_schema, dict):
            continue
        if raw_schema.get("type") == "string" and raw_schema.get("format") == "binary":
            result.append(
                MultipartFileMapping(
                    part_name=name,
                    content_field=name,
                    default_filename=f"{name}.bin",
                    required=name in required_names,
                )
            )
    return result


def _select_request_media(operation: CanonicalOperation) -> CanonicalMediaType | None:
    if operation.request_body is None:
        return None
    by_type = {item.media_type.casefold(): item for item in operation.request_body.content}
    for media_type in _SUPPORTED_MEDIA_TYPES:
        if media_type in by_type:
            return by_type[media_type]
    declared = ", ".join(sorted(by_type)) or "none"
    raise _compile_error(operation, f"unsupported request media types: {declared}")


def _hoist_definitions(
    schema: JsonObject,
    definitions: JsonObject,
    operation: CanonicalOperation,
) -> None:
    raw_definitions = schema.pop("$defs", None)
    if raw_definitions is None:
        return
    if not isinstance(raw_definitions, dict):
        raise _compile_error(operation, "JSON Schema $defs must be an object")
    for name, definition in raw_definitions.items():
        existing = definitions.get(name)
        if existing is not None and existing != definition:
            raise _compile_error(operation, f"conflicting JSON Schema definition {name!r}")
        definitions[name] = definition


def _responses(operation: CanonicalOperation) -> tuple[list[ResponseDefinition], JsonObject | None]:
    definitions: list[ResponseDefinition] = []
    success_body_schemas: list[JsonObject] = []
    envelope_definitions: JsonObject = {}
    for response in sorted(operation.responses, key=lambda item: item.status_code):
        if not response.content:
            definitions.append(
                ResponseDefinition(
                    status_code=response.status_code,
                    description=response.description,
                )
            )
            if _response_can_be_success(response.status_code):
                success_body_schemas.append({"type": "null"})
            continue
        for media in sorted(response.content, key=lambda item: item.media_type):
            normalized_media = media.media_type.split(";", 1)[0].strip().casefold()
            if _response_can_be_success(response.status_code) and not _supported_response_media(
                normalized_media
            ):
                raise _compile_error(
                    operation,
                    f"successful response media type {normalized_media!r} is unsupported",
                )
            definitions.append(
                ResponseDefinition(
                    status_code=response.status_code,
                    media_type=normalized_media,
                    schema=media.schema_,
                    description=response.description,
                )
            )
            if _response_can_be_success(response.status_code):
                if media.schema_:
                    envelope_schema: JsonObject = deepcopy(media.schema_)
                elif normalized_media.startswith("text/"):
                    envelope_schema = {"type": "string"}
                else:
                    envelope_schema = {}
                _hoist_definitions(envelope_schema, envelope_definitions, operation)
                success_body_schemas.append(envelope_schema)
    return definitions, _response_envelope_schema(
        success_body_schemas,
        definitions=envelope_definitions,
    )


def _response_can_be_success(status_code: str) -> bool:
    normalized = status_code.upper()
    return normalized == "DEFAULT" or normalized.startswith("2")


def _supported_response_media(media_type: str) -> bool:
    return (
        media_type == "application/json"
        or media_type.endswith("+json")
        or media_type.startswith("text/")
    )


def _response_envelope_schema(
    body_schemas: list[JsonObject],
    *,
    definitions: JsonObject,
) -> JsonObject | None:
    if not body_schemas:
        return None
    unique: list[JsonObject] = []
    seen: set[bytes] = set()
    for schema in body_schemas:
        identity = canonical_json_bytes(schema)
        if identity not in seen:
            seen.add(identity)
            unique.append(schema)
    # Response dispatch has already selected the exact status/media schema.
    # The public envelope is therefore an inclusive union: overlapping source
    # schemas are valid and must not become impossible through JSON Schema's
    # exclusive ``oneOf`` semantics.
    body_schema = unique[0] if len(unique) == 1 else cast(JsonObject, {"anyOf": unique})
    envelope: JsonObject = {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "contentType", "body"],
        "properties": {
            "status": {"type": "integer", "minimum": 200, "maximum": 299},
            "contentType": {"type": "string"},
            "body": body_schema,
        },
    }
    if definitions:
        envelope["$defs"] = definitions
    return envelope


def _compile_tool(
    operation: CanonicalOperation,
    *,
    profile_refs: Mapping[str, str],
    tool_name: str,
    timeout_ms: int,
    max_request_bytes: int,
    max_response_bytes: int,
) -> MCPTool:
    if operation.server_ref is None:
        raise _compile_error(
            operation,
            "upstream server selection is unresolved; configure an applicable server mapping",
        )
    properties: JsonObject = {}
    definitions: JsonObject = {}
    required: list[str] = []
    mappings: list[ParameterMapping] = []
    used_fields: set[str] = set()
    auth_ref = _operation_auth_ref(operation, profile_refs)

    for parameter in sorted(
        operation.parameters,
        key=lambda item: (item.location.value, item.name.casefold()),
    ):
        unsupported = parameter.schema_.get("x-mcplica-unsupported")
        if isinstance(unsupported, str):
            raise _compile_error(
                operation,
                f"parameter {parameter.name!r} uses unsupported construct {unsupported!r}",
            )
        if parameter.location is ParameterLocation.COOKIE:
            raise _compile_error(operation, "cookie parameters are not supported")
        if (
            parameter.location is ParameterLocation.HEADER
            and parameter.name.casefold() in _FORBIDDEN_CALLER_HEADERS
        ):
            if parameter.name.casefold() == "authorization" and auth_ref is not None:
                continue
            raise _compile_error(
                operation,
                f"caller-controlled header {parameter.name!r} is forbidden",
            )
        field_name = _unique_field_name(parameter.name, parameter.location, used_fields)
        field_schema = deepcopy(parameter.schema_)
        _hoist_definitions(field_schema, definitions, operation)
        if parameter.description and "description" not in field_schema:
            field_schema["description"] = parameter.description
        properties[field_name] = field_schema or {"type": "string"}
        if parameter.required:
            required.append(field_name)
        mappings.append(
            ParameterMapping(
                tool_field=field_name,
                source_name=parameter.name,
                target=ParameterTarget(parameter.location.value),
                required=parameter.required,
                style=parameter.style,
                explode=parameter.explode,
                allow_reserved=parameter.allow_reserved,
            )
        )

    body_mapping: RequestBodyMapping | None = None
    request_media = _select_request_media(operation)
    if request_media is not None:
        body_field = _unique_field_name("body", ParameterLocation.QUERY, used_fields)
        body_schema = deepcopy(request_media.schema_)
        _hoist_definitions(body_schema, definitions, operation)
        if request_media.media_type == "multipart/form-data":
            raw_properties = body_schema.get("properties")
            if isinstance(raw_properties, dict):
                for raw_property in raw_properties.values():
                    if (
                        isinstance(raw_property, dict)
                        and raw_property.get("type") == "string"
                        and raw_property.get("format") == "binary"
                    ):
                        raw_property["contentEncoding"] = "base64"
        properties[body_field] = body_schema
        assert operation.request_body is not None
        if operation.request_body.required:
            required.append(body_field)
        body_mapping = RequestBodyMapping(
            tool_field=body_field,
            media_type=cast(SupportedMediaType, request_media.media_type),
            required=operation.request_body.required,
            multipart_files=_multipart_files(request_media),
        )

    input_schema: JsonObject = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        input_schema["required"] = [cast(JsonValue, item) for item in sorted(set(required))]
    if definitions:
        input_schema["$defs"] = definitions
    responses, output_schema = _responses(operation)
    title = operation.semantic.title or operation.summary or tool_name.replace("_", " ").title()
    description = (
        operation.semantic.description
        or operation.description
        or operation.summary
        or f"{operation.method.value} {operation.path_template}"
    )
    return MCPTool(
        name=tool_name,
        title=title,
        description=description,
        input_schema=input_schema,
        output_schema=output_schema,
        responses=responses,
        operation_key=operation.key,
        request_mapping=RequestMapping(
            server_ref=operation.server_ref,
            method=operation.method,
            path=operation.path_template,
            parameters=mappings,
            body=body_mapping,
        ),
        security_profile_ref=auth_ref,
        timeout_ms=timeout_ms,
        max_request_bytes=max_request_bytes,
        max_response_bytes=max_response_bytes,
        provenance={
            "source_version_id": str(operation.provenance.operation.source_version_id),
            "source_pointer": operation.provenance.operation.pointer,
        },
    )


def _tool_names(operations: Sequence[CanonicalOperation]) -> dict[str, str]:
    grouped: dict[str, list[CanonicalOperation]] = {}
    for operation in operations:
        grouped.setdefault(operation.tool_name_seed, []).append(operation)
    result: dict[str, str] = {}
    used: set[str] = set()
    for base_name, matches in sorted(grouped.items()):
        for operation in sorted(matches, key=lambda item: item.key):
            candidate = base_name
            if len(matches) > 1 or candidate in used:
                suffix = hashlib.sha256(operation.key.encode()).hexdigest()[:8]
                candidate = f"{base_name[:110]}_{suffix}"
            if candidate in used:
                raise _compile_error(operation, "stable tool-name collision")
            used.add(candidate)
            result[operation.key] = candidate
    return result


def compile_manifest(
    api: CanonicalApi,
    *,
    project_id: str,
    project_name: str,
    project_slug: str,
    build_id: str,
    created_at: datetime,
    security_selections: Mapping[str, BuildSecuritySelection] | None = None,
    excluded_operation_keys: frozenset[str] = frozenset(),
    resources: Sequence[MCPResource] = (),
    source_digest: str | None = None,
    canonical_digest: str | None = None,
    compiler_version: str = COMPILER_VERSION,
    runtime_compatibility: str = RUNTIME_COMPATIBILITY,
    prompt_bundle_version: str | None = None,
    analysis_model: str | None = None,
    validation_model: str | None = None,
    embedding_model: str | None = None,
    timeout_ms: int = 30_000,
    max_request_bytes: int = 10_000_000,
    max_response_bytes: int = 2_000_000,
) -> MCPManifest:
    if str(api.project_id) != project_id:
        raise CompilationError("Canonical project identity does not match compiler input")
    unknown_exclusions = excluded_operation_keys - {item.key for item in api.operations}
    if unknown_exclusions:
        raise CompilationError(
            "Exclusions reference operations absent from the canonical snapshot",
            details={"operation_keys": sorted(unknown_exclusions)},
        )
    executable = [
        operation for operation in api.operations if operation.key not in excluded_operation_keys
    ]
    profiles, profile_refs = _auth_profiles(api, security_selections or {}, executable)
    names = _tool_names(executable)
    tools = [
        _compile_tool(
            operation,
            profile_refs=profile_refs,
            tool_name=names[operation.key],
            timeout_ms=timeout_ms,
            max_request_bytes=max_request_bytes,
            max_response_bytes=max_response_bytes,
        )
        for operation in sorted(executable, key=lambda item: item.key)
    ]
    referenced_server_refs = {
        operation.server_ref for operation in executable if operation.server_ref is not None
    }
    known_server_refs = {server.key for server in api.servers}
    missing_servers = referenced_server_refs - known_server_refs
    if missing_servers:
        raise CompilationError(
            "Executable operations reference undefined servers",
            details={"server_refs": sorted(missing_servers)},
        )
    selected_servers = (
        [server for server in api.servers if server.key in referenced_server_refs]
        if referenced_server_refs
        else list(api.servers)
    )
    servers = [
        ServerDefinition(id=server.key, url=server.url, description=server.description)
        for server in sorted(selected_servers, key=lambda item: item.key)
    ]
    hosts: list[str] = []
    for server in servers:
        hostname = urlsplit(str(server.url)).hostname
        if hostname is None:
            raise CompilationError(f"Server {server.id!r} has an invalid URL")
        normalized = hostname.rstrip(".").encode("idna").decode("ascii").lower()
        if normalized not in hosts:
            hosts.append(normalized)
    canonical_hash = canonical_digest or canonical_sha256(api)
    build = BuildMetadata(
        build_id=build_id,
        source_version_ids=[str(value) for value in api.provenance.source_version_ids],
        source_digest=source_digest or api.provenance.source_fingerprint,
        canonical_sha256=canonical_hash,
        created_at=created_at.isoformat(),
        compiler_version=compiler_version,
        prompt_bundle_version=prompt_bundle_version,
        analysis_model=analysis_model,
        validation_model=validation_model,
        embedding_model=embedding_model,
    )
    security = RuntimeSecurity(
        allowed_upstream_hosts=sorted(hosts),
        default_timeout_ms=timeout_ms,
        default_max_response_bytes=max_response_bytes,
    )
    unsigned = {
        "schema_version": "mcp-manifest/v1",
        "project": {"id": project_id, "name": project_name, "slug": project_slug},
        "runtime_compatibility": runtime_compatibility,
        "servers": [item.model_dump(mode="json", by_alias=True) for item in servers],
        "auth_profiles": [item.model_dump(mode="json", by_alias=True) for item in profiles],
        "tools": [item.model_dump(mode="json", by_alias=True) for item in tools],
        "resources": [item.model_dump(mode="json", by_alias=True) for item in resources],
        "security": security.model_dump(mode="json", by_alias=True),
        "build": build.model_dump(mode="json", by_alias=True),
    }
    manifest_id = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    return MCPManifest(
        manifest_id=manifest_id,
        project=ManifestProject(id=project_id, name=project_name, slug=project_slug),
        runtime_compatibility=runtime_compatibility,
        servers=servers,
        auth_profiles=profiles,
        tools=tools,
        resources=list(resources),
        security=security,
        build=build,
    )
