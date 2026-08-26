import hashlib
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal, cast
from urllib.parse import urldefrag, urlsplit
from uuid import UUID

from jsonschema import Draft202012Validator, SchemaError
from jsonschema_path import SchemaPath
from mcp_contracts import (
    CanonicalApi,
    CanonicalMediaType,
    CanonicalOperation,
    CanonicalParameter,
    CanonicalProvenance,
    CanonicalRequestBody,
    CanonicalResponse,
    CanonicalSchema,
    CanonicalSecurityRequirement,
    CanonicalSecurityScheme,
    CanonicalServer,
    HttpMethod,
    OperationProvenance,
    ParameterLocation,
    SecuritySchemeType,
    SourceRef,
)
from mcp_contracts.json_types import JsonObject, JsonValue
from openapi_spec_validator import OpenAPIV30SpecValidator, OpenAPIV31SpecValidator
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError
from pydantic import AnyHttpUrl, TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from referencing.exceptions import Unresolvable, Unretrievable

from app.core.exceptions import ReferenceResolutionError, SourceParseError
from app.parsers.identifiers import (
    operation_key,
    pointer_token,
    schema_key,
    server_key,
    tool_name_seed,
)

HTTP_METHODS = frozenset(method.value.casefold() for method in HttpMethod)
SUPPORTED_BODY_MEDIA_TYPES = (
    "application/json",
    "application/x-www-form-urlencoded",
    "multipart/form-data",
)
_JSON_OBJECT: TypeAdapter[JsonObject] = TypeAdapter(JsonObject)
_JSON_VALUE: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
_HTTP_URL: TypeAdapter[AnyHttpUrl] = TypeAdapter(AnyHttpUrl)


@dataclass(frozen=True, slots=True)
class ExternalOpenApiDocument:
    document: JsonObject
    source_version_id: UUID


@dataclass(frozen=True, slots=True)
class _Resolved:
    value: JsonObject
    document: JsonObject
    source_version_id: UUID
    pointer: str


class OpenApiReferenceResolver:
    def __init__(
        self,
        root_document: JsonObject,
        root_source_version_id: UUID,
        external_documents: Mapping[str, ExternalOpenApiDocument] | None = None,
    ) -> None:
        self._root_document = root_document
        self._root_source_version_id = root_source_version_id
        self._external = dict(external_documents or {})

    @staticmethod
    def _pointer(document: JsonObject, pointer: str) -> JsonValue:
        if pointer in {"", "#"}:
            return document
        normalized = pointer[1:] if pointer.startswith("#") else pointer
        if not normalized.startswith("/"):
            raise ReferenceResolutionError(f"Unsupported JSON pointer: {pointer}")
        node: JsonValue = document
        for token in normalized[1:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, dict) or token not in node:
                raise ReferenceResolutionError(f"Unresolved $ref pointer: {pointer}")
            node = node[token]
        return node

    def resolve(
        self,
        value: JsonValue,
        *,
        document: JsonObject | None = None,
        source_version_id: UUID | None = None,
        pointer: str,
        seen: frozenset[tuple[UUID, str]] = frozenset(),
    ) -> _Resolved:
        current_document = document or self._root_document
        current_source_id = source_version_id or self._root_source_version_id
        if not isinstance(value, dict):
            raise ReferenceResolutionError(f"Expected an object at {pointer}")
        if "$ref" not in value:
            return _Resolved(value, current_document, current_source_id, pointer)
        raw_ref = value.get("$ref")
        if not isinstance(raw_ref, str) or not raw_ref:
            raise ReferenceResolutionError(f"Invalid $ref at {pointer}")
        target_document, target_source_id, target_pointer = self._reference_target(
            raw_ref,
            document=current_document,
            source_version_id=current_source_id,
        )
        identity = (target_source_id, target_pointer)
        if identity in seen:
            raise ReferenceResolutionError(f"Circular non-schema $ref: {raw_ref}")
        target = self._pointer(target_document, target_pointer)
        return self.resolve(
            target,
            document=target_document,
            source_version_id=target_source_id,
            pointer=target_pointer,
            seen=seen | {identity},
        )

    def _reference_target(
        self,
        raw_ref: str,
        *,
        document: JsonObject,
        source_version_id: UUID,
    ) -> tuple[JsonObject, UUID, str]:
        document_ref, fragment = urldefrag(raw_ref)
        if document_ref:
            parsed = urlsplit(document_ref)
            external = next(
                (
                    value
                    for candidate in (
                        document_ref,
                        parsed.path.lstrip("/"),
                        parsed.path.rsplit("/", 1)[-1],
                    )
                    if (value := self._external.get(candidate)) is not None
                ),
                None,
            )
            if external is None:
                raise ReferenceResolutionError(
                    "External $ref was not captured as an immutable source dependency: "
                    f"{document_ref}"
                )
            target_document = external.document
            target_source_id = external.source_version_id
        else:
            target_document = document
            target_source_id = source_version_id
        return target_document, target_source_id, f"#{fragment}" if fragment else "#"

    def materialize_schema(
        self,
        value: JsonValue,
        *,
        document: JsonObject,
        source_version_id: UUID,
        location: str,
    ) -> JsonObject:
        root = _json_object(value, location=location)
        definitions: JsonObject = {}
        building: set[tuple[UUID, str]] = set()

        def visit(
            node: JsonValue,
            *,
            current_document: JsonObject,
            current_source_id: UUID,
        ) -> JsonValue:
            if isinstance(node, list):
                return [
                    visit(
                        item,
                        current_document=current_document,
                        current_source_id=current_source_id,
                    )
                    for item in node
                ]
            if not isinstance(node, dict):
                return node
            output: JsonObject = {}
            raw_ref = node.get("$ref")
            if raw_ref is not None:
                if not isinstance(raw_ref, str) or not raw_ref:
                    raise ReferenceResolutionError(f"Invalid schema $ref at {location}")
                target_document, target_source_id, target_pointer = self._reference_target(
                    raw_ref,
                    document=current_document,
                    source_version_id=current_source_id,
                )
                identity = (target_source_id, target_pointer)
                definition_key = (
                    "mcplica_ref_"
                    + hashlib.sha256(f"{target_source_id}:{target_pointer}".encode()).hexdigest()[
                        :20
                    ]
                )
                if definition_key not in definitions:
                    definitions[definition_key] = {}
                    if identity not in building:
                        building.add(identity)
                        target = self._pointer(target_document, target_pointer)
                        target_schema = _json_object(target, location=target_pointer)
                        definitions[definition_key] = visit(
                            target_schema,
                            current_document=target_document,
                            current_source_id=target_source_id,
                        )
                        building.remove(identity)
                output["$ref"] = f"#/$defs/{definition_key}"
            for key, item in node.items():
                if key == "$ref":
                    continue
                output[key] = visit(
                    item,
                    current_document=current_document,
                    current_source_id=current_source_id,
                )
            return output

        materialized = visit(
            root,
            current_document=document,
            current_source_id=source_version_id,
        )
        assert isinstance(materialized, dict)
        if definitions:
            existing_defs = materialized.get("$defs")
            if existing_defs is not None and not isinstance(existing_defs, dict):
                raise SourceParseError(f"JSON Schema $defs at {location} must be an object")
            materialized["$defs"] = {**(existing_defs or {}), **definitions}
        return materialized


def _validate_openapi_spec(
    document: JsonObject,
    *,
    version: str,
    external_documents: Mapping[str, ExternalOpenApiDocument] | None,
) -> None:
    captured = dict(external_documents or {})

    def load_captured(uri: str) -> JsonObject:
        document_ref, _ = urldefrag(str(uri))
        parsed = urlsplit(document_ref)
        candidates = (
            document_ref,
            parsed.path.lstrip("/"),
            parsed.path.rsplit("/", 1)[-1],
        )
        for candidate in candidates:
            external = captured.get(candidate)
            if external is not None:
                return external.document
        raise KeyError(document_ref)

    handlers = {
        "": load_captured,
        "http": load_captured,
        "https": load_captured,
    }
    try:
        schema_path = SchemaPath.from_dict(document, handlers=handlers)
        validator = (
            OpenAPIV30SpecValidator(schema_path)
            if version.startswith("3.0.")
            else OpenAPIV31SpecValidator(schema_path)
        )
        validator.validate()
    except (Unresolvable, Unretrievable, KeyError) as exc:
        raise ReferenceResolutionError(
            "OpenAPI contains an external reference that was not captured as an immutable "
            "source dependency"
        ) from exc
    except OpenAPIValidationError as exc:
        location = getattr(exc, "json_path", None)
        details: JsonObject = {"source_location": str(location or "$")}
        raise SourceParseError(
            f"OpenAPI specification validation failed at {location or '$'}: {exc.message}",
            details=details,
        ) from exc


def _source_ref(source_version_id: UUID, pointer: str) -> SourceRef:
    return SourceRef(source_version_id=source_version_id, pointer=pointer)


def _json_object(value: object, *, location: str) -> JsonObject:
    try:
        return _JSON_OBJECT.validate_python(deepcopy(value), strict=True)
    except PydanticValidationError as exc:
        raise SourceParseError(f"Expected a JSON object at {location}") from exc


def _json_value(value: object, *, location: str) -> JsonValue:
    try:
        return _JSON_VALUE.validate_python(deepcopy(value), strict=True)
    except PydanticValidationError as exc:
        raise SourceParseError(f"Expected a JSON value at {location}") from exc


def _http_url(value: str, *, location: str) -> AnyHttpUrl:
    try:
        return _HTTP_URL.validate_python(value)
    except PydanticValidationError as exc:
        raise SourceParseError(f"Expected an absolute HTTP URL at {location}") from exc


def _schema(
    value: JsonValue | None,
    *,
    resolver: OpenApiReferenceResolver,
    document: JsonObject,
    source_version_id: UUID,
    location: str,
) -> JsonObject:
    schema = resolver.materialize_schema(
        value if value is not None else {},
        document=document,
        source_version_id=source_version_id,
        location=location,
    )
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise SourceParseError(
            f"Invalid JSON Schema at {location}: {exc.message}",
            details={"source_pointer": location},
        ) from exc
    return schema


def _server_url(raw: JsonObject, pointer: str) -> str:
    value = raw.get("url")
    if not isinstance(value, str) or not value:
        raise SourceParseError(f"OpenAPI server at {pointer} must define url")
    variables = raw.get("variables", {})
    if variables is not None and not isinstance(variables, dict):
        raise SourceParseError(f"OpenAPI server variables at {pointer} must be an object")
    resolved = value
    for name, raw_variable in (variables or {}).items():
        if not isinstance(raw_variable, dict) or "default" not in raw_variable:
            raise SourceParseError(
                f"OpenAPI server variable {name!r} at {pointer} requires a default"
            )
        resolved = resolved.replace("{" + name + "}", str(raw_variable["default"]))
    if "{" in resolved or "}" in resolved:
        raise SourceParseError(f"OpenAPI server at {pointer} has unresolved variables")
    return resolved.rstrip("/")


def _security_scheme(
    raw: JsonObject,
    *,
    source_ref: SourceRef,
) -> CanonicalSecurityScheme:
    scheme_type = raw.get("type")
    if scheme_type == "http":
        scheme = str(raw.get("scheme", "")).casefold()
        if scheme == "bearer":
            normalized_type = SecuritySchemeType.HTTP_BEARER
        elif scheme == "basic":
            normalized_type = SecuritySchemeType.HTTP_BASIC
        else:
            normalized_type = SecuritySchemeType.UNSUPPORTED
        return CanonicalSecurityScheme(
            type=normalized_type,
            scheme=scheme or None,
            source_ref=source_ref,
        )
    if scheme_type == "apiKey":
        location = raw.get("in")
        name = raw.get("name")
        if location not in {"header", "query", "cookie"} or not isinstance(name, str):
            return CanonicalSecurityScheme(
                type=SecuritySchemeType.UNSUPPORTED,
                scheme="apiKey",
                source_ref=source_ref,
            )
        return CanonicalSecurityScheme(
            type=SecuritySchemeType.API_KEY,
            location=cast(Literal["header", "query", "cookie"], location),
            name=name,
            source_ref=source_ref,
        )
    if scheme_type == "oauth2":
        flows = raw.get("flows")
        client_credentials = flows.get("clientCredentials") if isinstance(flows, dict) else None
        token_url = (
            client_credentials.get("tokenUrl") if isinstance(client_credentials, dict) else None
        )
        raw_scopes = (
            client_credentials.get("scopes") if isinstance(client_credentials, dict) else None
        )
        scopes = sorted(raw_scopes) if isinstance(raw_scopes, dict) else []
        if isinstance(token_url, str):
            return CanonicalSecurityScheme(
                type=SecuritySchemeType.OAUTH2_CLIENT_CREDENTIALS,
                token_url=_http_url(token_url, location=f"{source_ref.pointer}/flows"),
                scopes=scopes,
                source_ref=source_ref,
            )
    return CanonicalSecurityScheme(
        type=SecuritySchemeType.UNSUPPORTED,
        scheme=str(scheme_type) if scheme_type is not None else None,
        source_ref=source_ref,
    )


def _media_types(
    content: JsonValue | None,
    *,
    resolver: OpenApiReferenceResolver,
    document: JsonObject,
    source_version_id: UUID,
    pointer: str,
) -> list[CanonicalMediaType]:
    if content is None:
        return []
    if not isinstance(content, dict):
        raise SourceParseError(f"Media content at {pointer} must be an object")
    result: list[CanonicalMediaType] = []
    for media_type, raw_media in content.items():
        media_pointer = f"{pointer}/{pointer_token(str(media_type))}"
        if not isinstance(raw_media, dict):
            raise SourceParseError(f"Media definition at {media_pointer} must be an object")
        schema = _schema(
            raw_media.get("schema", {}),
            resolver=resolver,
            document=document,
            source_version_id=source_version_id,
            location=f"{media_pointer}/schema",
        )
        raw_examples = raw_media.get("examples")
        examples: list[JsonValue] = []
        if isinstance(raw_examples, dict):
            for example in raw_examples.values():
                if isinstance(example, dict) and "value" in example:
                    examples.append(
                        _json_value(example["value"], location=f"{media_pointer}/examples")
                    )
        elif "example" in raw_media:
            examples.append(_json_value(raw_media["example"], location=f"{media_pointer}/example"))
        result.append(
            CanonicalMediaType(
                media_type=str(media_type),
                schema=schema,
                examples=examples,
                source_ref=_source_ref(source_version_id, media_pointer),
            )
        )
    return result


def parse_openapi(
    document: Mapping[str, object],
    *,
    project_id: UUID,
    source_version_id: UUID,
    content_sha256: str,
    active_server_ref: str | None = None,
    default_base_url: str | None = None,
    external_documents: Mapping[str, ExternalOpenApiDocument] | None = None,
) -> CanonicalApi:
    root_document = _json_object(document, location="#")
    version = root_document.get("openapi")
    if not isinstance(version, str) or not (
        version.startswith("3.0.") or version.startswith("3.1.")
    ):
        raise SourceParseError("Supported OpenAPI sources must declare version 3.0.x or 3.1.x")
    info = root_document.get("info")
    if not isinstance(info, dict) or not isinstance(info.get("title"), str):
        raise SourceParseError("OpenAPI info.title is required")
    paths = root_document.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise SourceParseError("OpenAPI paths must be a non-empty object")

    _validate_openapi_spec(
        root_document,
        version=version,
        external_documents=external_documents,
    )

    resolver = OpenApiReferenceResolver(root_document, source_version_id, external_documents)
    servers: dict[str, CanonicalServer] = {}

    def register_servers(
        raw_servers: JsonValue | None,
        pointer: str,
        *,
        server_source_version_id: UUID,
    ) -> list[str]:
        if raw_servers is None:
            return []
        if not isinstance(raw_servers, list):
            raise SourceParseError(f"OpenAPI servers at {pointer} must be an array")
        keys: list[str] = []
        for index, raw_server in enumerate(raw_servers):
            item_pointer = f"{pointer}/{index}"
            if not isinstance(raw_server, dict):
                raise SourceParseError(f"OpenAPI server at {item_pointer} must be an object")
            url = _server_url(raw_server, item_pointer)
            key = server_key(url)
            servers.setdefault(
                key,
                CanonicalServer(
                    key=key,
                    url=_http_url(url, location=item_pointer),
                    description=(
                        str(raw_server["description"])
                        if raw_server.get("description") is not None
                        else None
                    ),
                    source_ref=_source_ref(server_source_version_id, item_pointer),
                ),
            )
            keys.append(key)
        return keys

    global_server_keys = register_servers(
        root_document.get("servers"),
        "#/servers",
        server_source_version_id=source_version_id,
    )
    if not global_server_keys and default_base_url:
        key = server_key(default_base_url)
        servers[key] = CanonicalServer(
            key=key,
            url=_http_url(
                default_base_url,
                location="#/x-mcplica-project-default-base-url",
            ),
            description="Project default base URL",
            source_ref=_source_ref(source_version_id, "#/x-mcplica-project-default-base-url"),
        )
        global_server_keys = [key]
    if not global_server_keys:
        raise SourceParseError(
            "OpenAPI source has no server URL and the Project has no default base URL"
        )

    components = root_document.get("components") or {}
    if not isinstance(components, dict):
        raise SourceParseError("OpenAPI components must be an object")
    raw_security_schemes = components.get("securitySchemes") or {}
    if not isinstance(raw_security_schemes, dict):
        raise SourceParseError("OpenAPI securitySchemes must be an object")
    security_schemes: dict[str, CanonicalSecurityScheme] = {}
    for name, raw_scheme in raw_security_schemes.items():
        pointer = f"#/components/securitySchemes/{pointer_token(str(name))}"
        resolved = resolver.resolve(raw_scheme, pointer=pointer)
        security_schemes[str(name)] = _security_scheme(
            resolved.value,
            source_ref=_source_ref(resolved.source_version_id, resolved.pointer),
        )

    raw_schemas = components.get("schemas") or {}
    if not isinstance(raw_schemas, dict):
        raise SourceParseError("OpenAPI component schemas must be an object")
    schemas: dict[str, CanonicalSchema] = {}
    for name, raw_schema in raw_schemas.items():
        pointer = f"#/components/schemas/{pointer_token(str(name))}"
        key = schema_key(str(name))
        schemas[key] = CanonicalSchema(
            key=key,
            schema=_schema(
                raw_schema,
                resolver=resolver,
                document=root_document,
                source_version_id=source_version_id,
                location=pointer,
            ),
            source_ref=_source_ref(source_version_id, pointer),
        )

    operation_ids: set[str] = set()
    operations: list[CanonicalOperation] = []
    for raw_path, raw_path_item in paths.items():
        path = str(raw_path)
        path_pointer = f"#/paths/{pointer_token(path)}"
        path_item_resolved = resolver.resolve(raw_path_item, pointer=path_pointer)
        path_item = path_item_resolved.value
        inherited_parameters = path_item.get("parameters") or []
        if not isinstance(inherited_parameters, list):
            raise SourceParseError(f"Path parameters at {path_pointer} must be an array")
        resolved_path_pointer = path_item_resolved.pointer
        path_server_keys = register_servers(
            path_item.get("servers"),
            f"{resolved_path_pointer}/servers",
            server_source_version_id=path_item_resolved.source_version_id,
        )

        for raw_method, raw_operation in path_item.items():
            method = str(raw_method).casefold()
            if method not in HTTP_METHODS:
                continue
            operation_pointer = f"{path_pointer}/{method}"
            resolved_operation_pointer = f"{resolved_path_pointer}/{method}"
            resolved_operation = resolver.resolve(
                raw_operation,
                document=path_item_resolved.document,
                source_version_id=path_item_resolved.source_version_id,
                pointer=resolved_operation_pointer,
            )
            operation = resolved_operation.value
            raw_operation_id = operation.get("operationId")
            operation_id = str(raw_operation_id).strip() if raw_operation_id else None
            if operation_id:
                if operation_id in operation_ids:
                    raise SourceParseError(f"Duplicate OpenAPI operationId: {operation_id}")
                operation_ids.add(operation_id)
            key = operation_key(method, path, operation_id)

            operation_server_keys = register_servers(
                operation.get("servers"),
                f"{resolved_operation.pointer}/servers",
                server_source_version_id=resolved_operation.source_version_id,
            )
            candidates = operation_server_keys or path_server_keys or global_server_keys
            selected_server = active_server_ref or candidates[0]
            if selected_server not in servers:
                raise SourceParseError("Configured active server does not exist in OpenAPI source")

            merged_parameters: dict[
                tuple[str, str],
                tuple[JsonObject, SourceRef, JsonObject, UUID],
            ] = {}
            operation_parameters = operation.get("parameters") or []
            if not isinstance(operation_parameters, list):
                raise SourceParseError(
                    f"Operation parameters at {operation_pointer} must be an array"
                )
            parameter_inputs = [
                (
                    raw_parameter,
                    path_item_resolved.document,
                    path_item_resolved.source_version_id,
                    f"{path_item_resolved.pointer}/parameters/{index}",
                )
                for index, raw_parameter in enumerate(inherited_parameters)
            ]
            parameter_inputs.extend(
                (
                    raw_parameter,
                    resolved_operation.document,
                    resolved_operation.source_version_id,
                    f"{resolved_operation.pointer}/parameters/{index}",
                )
                for index, raw_parameter in enumerate(operation_parameters)
            )
            for (
                raw_parameter,
                parameter_document,
                parameter_source_id,
                parameter_pointer,
            ) in parameter_inputs:
                resolved_parameter = resolver.resolve(
                    raw_parameter,
                    document=parameter_document,
                    source_version_id=parameter_source_id,
                    pointer=parameter_pointer,
                )
                parameter = resolved_parameter.value
                name = parameter.get("name")
                location = parameter.get("in")
                if not isinstance(name, str) or location not in {
                    "path",
                    "query",
                    "header",
                    "cookie",
                }:
                    raise SourceParseError(f"Invalid parameter at {parameter_pointer}")
                merged_parameters[(name, str(location))] = (
                    parameter,
                    _source_ref(
                        resolved_parameter.source_version_id,
                        resolved_parameter.pointer,
                    ),
                    resolved_parameter.document,
                    resolved_parameter.source_version_id,
                )

            parameters: list[CanonicalParameter] = []
            for (name, location), (
                parameter,
                provenance,
                parameter_document,
                parameter_source_id,
            ) in merged_parameters.items():
                required = bool(parameter.get("required", False))
                if location == "path" and not required:
                    raise SourceParseError(
                        f"Path parameter {name!r} must be required",
                        details={"source_pointer": provenance.pointer},
                    )
                if "content" in parameter and "schema" not in parameter:
                    parameter_schema: JsonObject = {"x-mcplica-unsupported": "parameter-content"}
                else:
                    parameter_schema = _schema(
                        parameter.get("schema", {}),
                        resolver=resolver,
                        document=parameter_document,
                        source_version_id=parameter_source_id,
                        location=f"{provenance.pointer}/schema",
                    )
                parameters.append(
                    CanonicalParameter(
                        name=name,
                        location=ParameterLocation(location),
                        required=required,
                        schema=parameter_schema,
                        description=(
                            str(parameter["description"])
                            if parameter.get("description") is not None
                            else None
                        ),
                        style=(str(parameter["style"]) if parameter.get("style") else None),
                        explode=(
                            bool(parameter["explode"])
                            if parameter.get("explode") is not None
                            else None
                        ),
                        allow_reserved=bool(parameter.get("allowReserved", False)),
                        source_ref=provenance,
                    )
                )

            request_body: CanonicalRequestBody | None = None
            if "requestBody" in operation:
                raw_body = resolver.resolve(
                    operation["requestBody"],
                    document=resolved_operation.document,
                    source_version_id=resolved_operation.source_version_id,
                    pointer=f"{resolved_operation.pointer}/requestBody",
                )
                content = _media_types(
                    raw_body.value.get("content"),
                    resolver=resolver,
                    document=raw_body.document,
                    source_version_id=raw_body.source_version_id,
                    pointer=f"{raw_body.pointer}/content",
                )
                if not content:
                    raise SourceParseError(
                        f"Request body at {raw_body.pointer} must define content"
                    )
                request_body = CanonicalRequestBody(
                    required=bool(raw_body.value.get("required", False)),
                    description=(
                        str(raw_body.value["description"])
                        if raw_body.value.get("description") is not None
                        else None
                    ),
                    content=content,
                    source_ref=_source_ref(raw_body.source_version_id, raw_body.pointer),
                )

            raw_responses = operation.get("responses")
            if not isinstance(raw_responses, dict) or not raw_responses:
                raise SourceParseError(f"Operation at {operation_pointer} requires responses")
            responses: list[CanonicalResponse] = []
            for status_code, raw_response in raw_responses.items():
                response_pointer = (
                    f"{resolved_operation.pointer}/responses/{pointer_token(str(status_code))}"
                )
                resolved_response = resolver.resolve(
                    raw_response,
                    document=resolved_operation.document,
                    source_version_id=resolved_operation.source_version_id,
                    pointer=response_pointer,
                )
                responses.append(
                    CanonicalResponse(
                        status_code=str(status_code),
                        description=(
                            str(resolved_response.value["description"])
                            if resolved_response.value.get("description") is not None
                            else None
                        ),
                        content=_media_types(
                            resolved_response.value.get("content"),
                            resolver=resolver,
                            document=resolved_response.document,
                            source_version_id=resolved_response.source_version_id,
                            pointer=f"{resolved_response.pointer}/content",
                        ),
                        source_ref=_source_ref(
                            resolved_response.source_version_id,
                            resolved_response.pointer,
                        ),
                    )
                )

            operation_has_security = "security" in operation
            raw_security = operation.get("security", root_document.get("security", [])) or []
            security_source_id = (
                resolved_operation.source_version_id
                if operation_has_security
                else source_version_id
            )
            security_pointer = (
                f"{resolved_operation.pointer}/security" if operation_has_security else "#/security"
            )
            if not isinstance(raw_security, list):
                raise SourceParseError(f"Security at {operation_pointer} must be an array")
            security: list[CanonicalSecurityRequirement] = []
            for index, raw_requirement in enumerate(raw_security):
                if not isinstance(raw_requirement, dict):
                    raise SourceParseError(
                        f"Security requirement at {operation_pointer}/security/{index} "
                        "must be an object"
                    )
                scheme_scopes: dict[str, list[str]] = {}
                for scheme_name, raw_scopes in raw_requirement.items():
                    if not isinstance(raw_scopes, list):
                        raise SourceParseError("Security requirement scopes must be an array")
                    scheme_scopes[str(scheme_name)] = [str(scope) for scope in raw_scopes]
                security.append(
                    CanonicalSecurityRequirement(
                        scheme_scopes=scheme_scopes,
                        source_ref=_source_ref(
                            security_source_id,
                            f"{security_pointer}/{index}",
                        ),
                    )
                )

            executable_fields = {
                "method": _source_ref(
                    path_item_resolved.source_version_id,
                    resolved_operation_pointer,
                ),
                "path_template": _source_ref(source_version_id, path_pointer),
                "server_ref": servers[selected_server].source_ref,
            }
            raw_tags = operation.get("tags", [])
            if not isinstance(raw_tags, list) or not all(isinstance(tag, str) for tag in raw_tags):
                raise SourceParseError(f"Tags at {operation_pointer} must be text values")
            operations.append(
                CanonicalOperation(
                    key=key,
                    source_operation_id=operation_id,
                    tool_name_seed=tool_name_seed(method, path, operation_id),
                    method=HttpMethod(method.upper()),
                    path_template=path,
                    server_ref=selected_server,
                    summary=(
                        str(operation["summary"]) if operation.get("summary") is not None else None
                    ),
                    description=(
                        str(operation["description"])
                        if operation.get("description") is not None
                        else None
                    ),
                    parameters=parameters,
                    request_body=request_body,
                    responses=responses,
                    security=security,
                    tags=[cast(str, tag) for tag in raw_tags],
                    provenance=OperationProvenance(
                        operation=_source_ref(
                            resolved_operation.source_version_id,
                            resolved_operation.pointer,
                        ),
                        executable_fields=executable_fields,
                    ),
                )
            )

    if not operations:
        raise SourceParseError("OpenAPI source contains no executable operations")
    active_ref = active_server_ref
    if active_ref is None and len(servers) == 1:
        active_ref = next(iter(servers))
    return CanonicalApi(
        project_id=project_id,
        source_format="openapi-3.0" if version.startswith("3.0.") else "openapi-3.1",
        title=str(info["title"]),
        version=str(info["version"]) if info.get("version") is not None else None,
        description=(str(info["description"]) if info.get("description") is not None else None),
        servers=list(servers.values()),
        active_server_ref=active_ref,
        security_schemes=security_schemes,
        schemas=schemas,
        operations=operations,
        provenance=CanonicalProvenance(
            source_version_ids=[source_version_id],
            source_fingerprint=content_sha256,
        ),
    )
