import hashlib
import re
from typing import Any

from mcp_contracts.canonical import (
    CanonicalApi,
    CanonicalOperation,
    CanonicalParameter,
    CanonicalRequestBody,
    CanonicalServer,
    ParameterLocation,
)

from app.core.exceptions import ValidationError

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def _local_ref(document: dict[str, Any], ref: str) -> Any:
    if not ref.startswith("#/"):
        raise ValidationError(f"Remote/external $ref is not supported by starter parser: {ref}")
    node: Any = document
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        try:
            node = node[token]
        except (KeyError, TypeError) as exc:
            raise ValidationError(f"Unresolved $ref: {ref}") from exc
    return node


def _resolve(document: dict[str, Any], value: Any, seen: set[str] | None = None) -> Any:
    if isinstance(value, dict) and "$ref" in value:
        ref = str(value["$ref"])
        seen = set() if seen is None else seen
        if ref in seen:
            raise ValidationError(f"Cyclic $ref detected: {ref}")
        target = _local_ref(document, ref)
        return _resolve(document, target, {*seen, ref})
    return value


def _operation_key(method: str, path: str) -> str:
    normalized = f"{method.upper()} {path}"
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"op_{digest}"


def parse_openapi(document: dict[str, Any]) -> CanonicalApi:
    version = str(document.get("openapi", ""))
    if not (version.startswith("3.0.") or version.startswith("3.1.")):
        raise ValidationError("MCPlica starter supports OpenAPI 3.0.x and 3.1.x")

    info = document.get("info") or {}
    title = str(info.get("title") or "Imported API")

    raw_servers = document.get("servers") or []
    if not raw_servers:
        raise ValidationError("OpenAPI must define at least one server URL")
    servers = [
        CanonicalServer(key=f"server_{i}", url=str(item["url"]).rstrip("/"), description=item.get("description"))
        for i, item in enumerate(raw_servers)
        if isinstance(item, dict) and item.get("url")
    ]
    if not servers:
        raise ValidationError("No usable OpenAPI server URL found")

    security_schemes = (
        document.get("components", {}).get("securitySchemes", {})
        if isinstance(document.get("components"), dict)
        else {}
    )

    operations: list[CanonicalOperation] = []
    for path, path_item_raw in (document.get("paths") or {}).items():
        path_item = _resolve(document, path_item_raw)
        if not isinstance(path_item, dict):
            continue
        inherited_params = list(path_item.get("parameters") or [])

        for method, operation_raw in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation_raw, dict):
                continue
            operation = _resolve(document, operation_raw)
            raw_params = [*inherited_params, *(operation.get("parameters") or [])]
            parameters: list[CanonicalParameter] = []
            for item in raw_params:
                param = _resolve(document, item)
                if not isinstance(param, dict):
                    continue
                location = str(param.get("in", ""))
                if location not in {"path", "query", "header", "cookie"}:
                    raise ValidationError(f"Unsupported parameter location {location!r}")
                schema = _resolve(document, param.get("schema") or {})
                parameters.append(
                    CanonicalParameter(
                        name=str(param["name"]),
                        location=ParameterLocation(location),
                        required=bool(param.get("required") or location == "path"),
                        schema=schema,
                        description=param.get("description"),
                        style=param.get("style"),
                        explode=param.get("explode"),
                    )
                )

            request_body = None
            if "requestBody" in operation:
                raw_body = _resolve(document, operation["requestBody"])
                content = raw_body.get("content") or {}
                supported = [
                    mt
                    for mt in ("application/json", "application/x-www-form-urlencoded")
                    if mt in content
                ]
                if not supported:
                    raise ValidationError(
                        f"{method.upper()} {path}: unsupported request body media type"
                    )
                media_type = supported[0]
                body_schema = _resolve(document, content[media_type].get("schema") or {})
                request_body = CanonicalRequestBody(
                    required=bool(raw_body.get("required")),
                    media_type=media_type,
                    schema=body_schema,
                )

            response_schema = None
            for status, response_raw in (operation.get("responses") or {}).items():
                if not str(status).startswith("2"):
                    continue
                response = _resolve(document, response_raw)
                content = response.get("content") or {}
                if "application/json" in content:
                    response_schema = _resolve(document, content["application/json"].get("schema") or {})
                    break

            effective_security = operation.get("security", document.get("security", [])) or []
            security_names: list[str] = []
            for requirement in effective_security:
                if isinstance(requirement, dict):
                    security_names.extend(str(name) for name in requirement)

            operation_id = operation.get("operationId")
            summary = operation.get("summary") or operation_id or f"{method.upper()} {path}"
            operations.append(
                CanonicalOperation(
                    operation_key=_operation_key(method, path),
                    operation_id=str(operation_id) if operation_id else None,
                    method=method.upper(),
                    path=str(path),
                    title=str(summary),
                    description=operation.get("description"),
                    tags=[str(tag) for tag in operation.get("tags") or []],
                    parameters=parameters,
                    request_body=request_body,
                    response_schema=response_schema,
                    security_scheme_names=sorted(set(security_names)),
                    source_pointer=f"#/paths/{path.replace('/', '~1')}/{method.lower()}",
                )
            )

    if not operations:
        raise ValidationError("OpenAPI source contains no executable operations")

    return CanonicalApi(
        source_format=f"openapi-{version}",
        title=title,
        version=str(info.get("version")) if info.get("version") is not None else None,
        servers=servers,
        operations=operations,
        security_schemes=security_schemes,
    )
