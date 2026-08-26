import hashlib
from collections.abc import Mapping
from copy import deepcopy
from urllib.parse import urldefrag
from uuid import UUID

from jsonschema import Draft202012Validator, SchemaError
from mcp_contracts import (
    ApiInventory,
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
    OperationProvenance,
    SourceRef,
)
from mcp_contracts.json_types import JsonObject, JsonValue
from pydantic import AnyHttpUrl, TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import ReferenceResolutionError, SourceParseError
from app.parsers.identifiers import (
    operation_key,
    pointer_token,
    schema_key,
    tool_name_seed,
)


def _ref(source_version_id: UUID, pointer: str) -> SourceRef:
    return SourceRef(source_version_id=source_version_id, pointer=pointer)


_HTTP_URL = TypeAdapter(AnyHttpUrl)


def _validate_schema(schema: Mapping[str, object], pointer: str) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise SourceParseError(
            f"Invalid JSON Schema at {pointer}: {exc.message}",
            details={"source_pointer": pointer},
        ) from exc


def _pointer(document: JsonObject, pointer: str) -> JsonValue:
    if pointer in {"", "#"}:
        return document
    normalized = pointer[1:] if pointer.startswith("#") else pointer
    if not normalized.startswith("/"):
        raise ReferenceResolutionError(f"Unsupported API Inventory JSON pointer: {pointer}")
    node: JsonValue = document
    for token in normalized[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or token not in node:
            raise ReferenceResolutionError(f"Unresolved API Inventory $ref: {pointer}")
        node = node[token]
    return node


def _materialize_schema(
    schema: JsonObject,
    *,
    inventory_schemas: Mapping[str, JsonObject],
    source_version_id: UUID,
    location: str,
) -> JsonObject:
    definitions: JsonObject = {}
    building: set[tuple[str, str]] = set()

    def visit(
        node: JsonValue,
        *,
        resource_root: JsonObject,
        resource_id: str,
    ) -> JsonValue:
        if isinstance(node, list):
            return [
                visit(item, resource_root=resource_root, resource_id=resource_id) for item in node
            ]
        if not isinstance(node, dict):
            return node
        output: JsonObject = {}
        raw_ref = node.get("$ref")
        if raw_ref is not None:
            if not isinstance(raw_ref, str) or not raw_ref:
                raise ReferenceResolutionError(f"Invalid API Inventory $ref at {location}")
            document_ref, fragment = urldefrag(raw_ref)
            if document_ref:
                raise ReferenceResolutionError(
                    "API Inventory external schema refs require an immutable linked source"
                )
            target_pointer = f"#{fragment}" if fragment else "#"
            if target_pointer.startswith("#/schemas/"):
                encoded_name = target_pointer.removeprefix("#/schemas/").split("/", 1)[0]
                schema_name = encoded_name.replace("~1", "/").replace("~0", "~")
                target = inventory_schemas.get(schema_name)
                if target is None:
                    raise ReferenceResolutionError(
                        f"Unresolved API Inventory schema ref: {raw_ref}"
                    )
                target_root = target
                target_resource_id = f"#/schemas/{pointer_token(schema_name)}"
                remainder = target_pointer.removeprefix(f"#/schemas/{pointer_token(schema_name)}")
                nested_pointer = f"#{remainder}" if remainder else "#"
                target_node = _pointer(target_root, nested_pointer)
            else:
                target_root = resource_root
                target_resource_id = resource_id
                target_node = _pointer(resource_root, target_pointer)
            identity = (target_resource_id, target_pointer)
            definition_key = (
                "mcplica_ref_"
                + hashlib.sha256(
                    f"{source_version_id}:{target_resource_id}:{target_pointer}".encode()
                ).hexdigest()[:20]
            )
            if definition_key not in definitions:
                definitions[definition_key] = {}
                if identity not in building:
                    building.add(identity)
                    target_schema = (
                        deepcopy(target_node) if isinstance(target_node, dict) else target_node
                    )
                    if not isinstance(target_schema, dict):
                        raise ReferenceResolutionError(
                            f"API Inventory schema ref is not an object: {raw_ref}"
                        )
                    definitions[definition_key] = visit(
                        target_schema,
                        resource_root=target_root,
                        resource_id=target_resource_id,
                    )
                    building.remove(identity)
            output["$ref"] = f"#/$defs/{definition_key}"
        for key, item in node.items():
            if key in {"$ref", "$defs"}:
                continue
            output[key] = visit(
                item,
                resource_root=resource_root,
                resource_id=resource_id,
            )
        return output

    materialized = visit(
        deepcopy(schema),
        resource_root=schema,
        resource_id=location,
    )
    assert isinstance(materialized, dict)
    if definitions:
        materialized["$defs"] = definitions
    return materialized


def parse_api_inventory(
    document: Mapping[str, object],
    *,
    project_id: UUID,
    source_version_id: UUID,
    content_sha256: str,
    default_base_url: str | None = None,
    active_server_ref: str | None = None,
) -> CanonicalApi:
    try:
        inventory = ApiInventory.model_validate(document)
    except PydanticValidationError as exc:
        first = exc.errors(include_url=False)[0]
        location = "/".join(str(part) for part in first["loc"])
        raise SourceParseError(
            f"Invalid API Inventory at {location or 'root'}: {first['msg']}",
            details={"source_location": location, "errors": exc.error_count()},
        ) from exc

    servers: list[CanonicalServer] = []
    for index, server in enumerate(inventory.servers):
        servers.append(
            CanonicalServer(
                key=server.id,
                url=server.url,
                description=server.description,
                source_ref=_ref(source_version_id, f"#/servers/{index}"),
            )
        )
    if not servers and default_base_url:
        try:
            servers.append(
                CanonicalServer(
                    key="project_default",
                    url=_HTTP_URL.validate_python(default_base_url),
                    description="Project default base URL",
                    source_ref=_ref(
                        source_version_id,
                        "#/x-mcplica-project-default-base-url",
                    ),
                )
            )
        except PydanticValidationError as exc:
            raise SourceParseError("Project default base URL is invalid") from exc
    if not servers:
        raise SourceParseError(
            "API Inventory has no server and the Project has no default base URL"
        )
    server_keys = {server.key for server in servers}
    if active_server_ref is not None and active_server_ref not in server_keys:
        raise SourceParseError("Configured active server does not exist in API Inventory")

    security_schemes = {
        name: CanonicalSecurityScheme(
            **scheme.model_dump(mode="python"),
            source_ref=_ref(
                source_version_id,
                f"#/security_schemes/{pointer_token(name)}",
            ),
        )
        for name, scheme in inventory.security_schemes.items()
    }
    schemas: dict[str, CanonicalSchema] = {}
    for name, raw_schema in inventory.schemas.items():
        pointer = f"#/schemas/{pointer_token(name)}"
        schema = _materialize_schema(
            raw_schema,
            inventory_schemas=inventory.schemas,
            source_version_id=source_version_id,
            location=pointer,
        )
        _validate_schema(schema, pointer)
        key = schema_key(name)
        schemas[key] = CanonicalSchema(
            key=key,
            schema=schema,
            source_ref=_ref(source_version_id, pointer),
        )

    operations: list[CanonicalOperation] = []
    for index, operation in enumerate(inventory.operations):
        pointer = f"#/operations/{index}"
        parameters: list[CanonicalParameter] = []
        for parameter_index, parameter in enumerate(operation.parameters):
            parameter_pointer = f"{pointer}/parameters/{parameter_index}"
            schema = _materialize_schema(
                parameter.schema_,
                inventory_schemas=inventory.schemas,
                source_version_id=source_version_id,
                location=f"{parameter_pointer}/schema",
            )
            _validate_schema(schema, f"{parameter_pointer}/schema")
            parameters.append(
                CanonicalParameter(
                    name=parameter.name,
                    location=parameter.location,
                    required=parameter.required,
                    schema=schema,
                    description=parameter.description,
                    style=parameter.style,
                    explode=parameter.explode,
                    allow_reserved=parameter.allow_reserved,
                    source_ref=_ref(source_version_id, parameter_pointer),
                )
            )
        request_body: CanonicalRequestBody | None = None
        if operation.request_body is not None:
            body_pointer = f"{pointer}/request_body"
            body_schema = _materialize_schema(
                operation.request_body.schema_,
                inventory_schemas=inventory.schemas,
                source_version_id=source_version_id,
                location=f"{body_pointer}/schema",
            )
            _validate_schema(body_schema, f"{body_pointer}/schema")
            request_body = CanonicalRequestBody(
                required=operation.request_body.required,
                description=operation.request_body.description,
                content=[
                    CanonicalMediaType(
                        media_type=operation.request_body.content_type,
                        schema=body_schema,
                        source_ref=_ref(source_version_id, body_pointer),
                    )
                ],
                source_ref=_ref(source_version_id, body_pointer),
            )
        responses: list[CanonicalResponse] = []
        for status_code, response in sorted(operation.responses.items()):
            response_pointer = f"{pointer}/responses/{pointer_token(status_code)}"
            content: list[CanonicalMediaType] = []
            if response.schema_ is not None and response.content_type is not None:
                response_schema = _materialize_schema(
                    response.schema_,
                    inventory_schemas=inventory.schemas,
                    source_version_id=source_version_id,
                    location=f"{response_pointer}/schema",
                )
                _validate_schema(response_schema, f"{response_pointer}/schema")
                content.append(
                    CanonicalMediaType(
                        media_type=response.content_type,
                        schema=response_schema,
                        source_ref=_ref(source_version_id, response_pointer),
                    )
                )
            responses.append(
                CanonicalResponse(
                    status_code=status_code,
                    description=response.description,
                    content=content,
                    source_ref=_ref(source_version_id, response_pointer),
                )
            )
        requirements = [
            CanonicalSecurityRequirement(
                scheme_scopes={name: list(scopes) for name, scopes in requirement.items()},
                source_ref=_ref(source_version_id, f"{pointer}/security/{security_index}"),
            )
            for security_index, requirement in enumerate(operation.security)
        ]
        selected_server = operation.server_id or active_server_ref or servers[0].key
        key = operation_key(
            operation.method.value,
            operation.path,
            operation.operation_id,
        )
        operations.append(
            CanonicalOperation(
                key=key,
                source_operation_id=operation.operation_id,
                tool_name_seed=tool_name_seed(
                    operation.method.value,
                    operation.path,
                    operation.operation_id,
                ),
                method=operation.method,
                path_template=operation.path,
                server_ref=selected_server,
                summary=operation.summary,
                description=operation.description,
                parameters=parameters,
                request_body=request_body,
                responses=responses,
                security=requirements,
                tags=list(operation.tags),
                provenance=OperationProvenance(
                    operation=_ref(source_version_id, pointer),
                    executable_fields={
                        "method": _ref(source_version_id, f"{pointer}/method"),
                        "path_template": _ref(source_version_id, f"{pointer}/path"),
                        "server_ref": _ref(source_version_id, f"{pointer}/server_id"),
                    },
                ),
            )
        )
    return CanonicalApi(
        project_id=project_id,
        source_format="api-inventory/v1",
        title=inventory.name,
        version=inventory.version,
        description=inventory.description,
        servers=servers,
        active_server_ref=active_server_ref or (servers[0].key if len(servers) == 1 else None),
        security_schemes=security_schemes,
        schemas=schemas,
        operations=operations,
        provenance=CanonicalProvenance(
            source_version_ids=[source_version_id],
            source_fingerprint=content_sha256,
        ),
    )
