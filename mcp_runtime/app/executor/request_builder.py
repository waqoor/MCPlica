import base64
import binascii
import re
from dataclasses import dataclass
from typing import cast

from mcp_contracts import MCPTool, ParameterMapping
from mcp_contracts.manifest import ParameterTarget

from app.auth.upstream import AuthInjection
from app.executor.errors import ArgumentValidationError
from app.security.url_policy import UpstreamUrlPolicy, encode_path_value

_HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_MEDIA_TYPE = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")
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


@dataclass(frozen=True, slots=True)
class QueryParameter:
    name: str
    value: str
    allow_reserved: bool = False


@dataclass(frozen=True, slots=True)
class MultipartPart:
    name: str
    content: bytes
    filename: str | None = None
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class BuiltRequest:
    method: str
    url: str
    headers: tuple[tuple[str, str], ...]
    query: tuple[QueryParameter, ...]
    json_body: object | None = None
    form_body: tuple[tuple[str, str], ...] | None = None
    multipart_body: tuple[MultipartPart, ...] | None = None


def _scalar(value: object, *, field: str) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str | int | float):
        return str(value)
    raise ArgumentValidationError(f"Field {field!r} cannot be serialized as a scalar")


def _array(value: list[object], *, field: str) -> list[str]:
    return [_scalar(item, field=field) for item in value]


def _object(value: dict[object, object], *, field: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for raw_name in sorted(value, key=str):
        if not isinstance(raw_name, str):
            raise ArgumentValidationError(f"Field {field!r} object keys must be strings")
        items.append((raw_name, _scalar(value[raw_name], field=field)))
    return items


def _style(parameter: ParameterMapping) -> tuple[str, bool]:
    if parameter.target == ParameterTarget.QUERY:
        return (
            parameter.style or "form",
            parameter.explode if parameter.explode is not None else True,
        )
    return (
        parameter.style or "simple",
        parameter.explode if parameter.explode is not None else False,
    )


def _path_value(parameter: ParameterMapping, value: object) -> str:
    style, explode = _style(parameter)
    if style != "simple":
        raise ArgumentValidationError("Path parameters support only simple serialization")
    if isinstance(value, list):
        return ",".join(encode_path_value(item) for item in cast(list[object], value))
    if isinstance(value, dict):
        items = _object(cast(dict[object, object], value), field=parameter.tool_field)
        if explode:
            return ",".join(
                f"{encode_path_value(name)}={encode_path_value(item)}" for name, item in items
            )
        flattened = [component for pair in items for component in pair]
        return ",".join(encode_path_value(component) for component in flattened)
    return encode_path_value(_scalar(value, field=parameter.tool_field))


def _query_values(parameter: ParameterMapping, value: object) -> list[QueryParameter]:
    style, explode = _style(parameter)
    name = parameter.source_name
    reserved = parameter.allow_reserved
    if isinstance(value, list):
        values = _array(cast(list[object], value), field=parameter.tool_field)
        if style == "form" and explode:
            return [QueryParameter(name, item, reserved) for item in values]
        delimiter = {"form": ",", "spaceDelimited": " ", "pipeDelimited": "|"}.get(style)
        if delimiter is None:
            raise ArgumentValidationError("Array query parameter uses an unsupported style")
        return [QueryParameter(name, delimiter.join(values), reserved)]
    if isinstance(value, dict):
        items = _object(cast(dict[object, object], value), field=parameter.tool_field)
        if style == "deepObject":
            return [QueryParameter(f"{name}[{key}]", item, reserved) for key, item in items]
        if style == "form" and explode:
            return [QueryParameter(key, item, reserved) for key, item in items]
        delimiter = {"form": ",", "spaceDelimited": " ", "pipeDelimited": "|"}.get(style)
        if delimiter is None:
            raise ArgumentValidationError("Object query parameter uses an unsupported style")
        flattened = [component for pair in items for component in pair]
        return [QueryParameter(name, delimiter.join(flattened), reserved)]
    if style not in {"form", "spaceDelimited", "pipeDelimited"}:
        raise ArgumentValidationError("Scalar query parameter uses an unsupported style")
    return [QueryParameter(name, _scalar(value, field=parameter.tool_field), reserved)]


def _header_value(parameter: ParameterMapping, value: object) -> str:
    style, explode = _style(parameter)
    if style != "simple":
        raise ArgumentValidationError("Header parameters support only simple serialization")
    if isinstance(value, list):
        return ",".join(_array(cast(list[object], value), field=parameter.tool_field))
    if isinstance(value, dict):
        items = _object(cast(dict[object, object], value), field=parameter.tool_field)
        if explode:
            return ",".join(f"{name}={item}" for name, item in items)
        return ",".join(component for pair in items for component in pair)
    return _scalar(value, field=parameter.tool_field)


def _validate_header(name: str, value: str) -> None:
    if not _HEADER_NAME.fullmatch(name):
        raise ArgumentValidationError("Manifest contains an invalid header name")
    if any(character in value for character in "\r\n\x00"):
        raise ArgumentValidationError("Header value contains forbidden characters")


def _apply_auth(
    headers: list[tuple[str, str]],
    query: list[QueryParameter],
    auth: AuthInjection,
) -> None:
    existing_headers = {name.lower() for name, _ in headers}
    existing_query = {parameter.name for parameter in query}
    for name, value in auth.headers:
        _validate_header(name, value)
        if name.lower() in existing_headers:
            raise ArgumentValidationError("Caller mapping conflicts with upstream authentication")
        headers.append((name, value))
        existing_headers.add(name.lower())
    for name, value in auth.query:
        if name in existing_query:
            raise ArgumentValidationError("Caller mapping conflicts with upstream authentication")
        query.append(QueryParameter(name, value))
        existing_query.add(name)


def _form_fields(raw_body: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw_body, dict):
        raise ArgumentValidationError("Form body must be an object")
    fields: list[tuple[str, str]] = []
    body = cast(dict[object, object], raw_body)
    for name, value in _object_mapping(body).items():
        if isinstance(value, list):
            fields.extend((name, _scalar(item, field=name)) for item in cast(list[object], value))
        else:
            fields.append((name, _scalar(value, field=name)))
    return tuple(fields)


def _object_mapping(value: dict[object, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ArgumentValidationError("Request body field names must be strings")
        result[key] = item
    return result


def _multipart_parts(tool: MCPTool, raw_body: object) -> tuple[MultipartPart, ...]:
    if not isinstance(raw_body, dict):
        raise ArgumentValidationError("Multipart body must be an object")
    body = tool.request_mapping.body
    assert body is not None
    values = _object_mapping(cast(dict[object, object], raw_body))
    consumed: set[str] = set()
    parts: list[MultipartPart] = []
    for file_mapping in body.multipart_files:
        content_value = values.get(file_mapping.content_field)
        if content_value is None:
            if file_mapping.required:
                raise ArgumentValidationError(
                    f"Missing multipart file field {file_mapping.content_field!r}"
                )
            continue
        if not isinstance(content_value, str):
            raise ArgumentValidationError("Multipart file content must be base64 text")
        try:
            content = base64.b64decode(content_value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ArgumentValidationError("Multipart file content is not valid base64") from exc
        filename_value = (
            values.get(file_mapping.filename_field)
            if file_mapping.filename_field is not None
            else file_mapping.default_filename
        )
        content_type_value = (
            values.get(file_mapping.content_type_field)
            if file_mapping.content_type_field is not None
            else file_mapping.default_content_type
        )
        if not isinstance(filename_value, str) or not filename_value:
            raise ArgumentValidationError("Multipart filename must be non-empty text")
        if any(character in filename_value for character in '\r\n\x00/\\"'):
            raise ArgumentValidationError("Multipart filename contains forbidden characters")
        if not isinstance(content_type_value, str) or not _MEDIA_TYPE.fullmatch(content_type_value):
            raise ArgumentValidationError("Multipart content type is invalid")
        consumed.add(file_mapping.content_field)
        if file_mapping.filename_field:
            consumed.add(file_mapping.filename_field)
        if file_mapping.content_type_field:
            consumed.add(file_mapping.content_type_field)
        parts.append(
            MultipartPart(
                file_mapping.part_name,
                content,
                filename=filename_value,
                content_type=content_type_value,
            )
        )
    for name, value in values.items():
        if name in consumed:
            continue
        if isinstance(value, list):
            parts.extend(
                MultipartPart(name, _scalar(item, field=name).encode("utf-8"))
                for item in cast(list[object], value)
            )
        else:
            parts.append(MultipartPart(name, _scalar(value, field=name).encode("utf-8")))
    return tuple(parts)


def build_request(
    tool: MCPTool,
    arguments: dict[str, object],
    policy: UpstreamUrlPolicy,
    auth: AuthInjection,
) -> BuiltRequest:
    mapping = tool.request_mapping
    mapped_fields = {parameter.tool_field for parameter in mapping.parameters}
    if mapping.body is not None:
        mapped_fields.add(mapping.body.tool_field)
    undeclared = sorted(set(arguments) - mapped_fields)
    if undeclared:
        raise ArgumentValidationError(f"Undeclared tool arguments are forbidden: {undeclared}")

    path = mapping.path
    query: list[QueryParameter] = []
    headers: list[tuple[str, str]] = [("Accept", "application/json, text/plain;q=0.9, */*;q=0.1")]
    for parameter in mapping.parameters:
        if parameter.required and parameter.tool_field not in arguments:
            raise ArgumentValidationError(f"Missing required field {parameter.tool_field!r}")
        if parameter.tool_field not in arguments:
            continue
        value = arguments[parameter.tool_field]
        if parameter.target == ParameterTarget.PATH:
            placeholder = "{" + parameter.source_name + "}"
            if placeholder not in path:
                raise ArgumentValidationError("Manifest path mapping is inconsistent")
            path = path.replace(placeholder, _path_value(parameter, value))
        elif parameter.target == ParameterTarget.QUERY:
            query.extend(_query_values(parameter, value))
        elif parameter.target == ParameterTarget.HEADER:
            if parameter.source_name.lower() in _FORBIDDEN_CALLER_HEADERS:
                raise ArgumentValidationError("Caller-controlled security header is forbidden")
            header_value = _header_value(parameter, value)
            _validate_header(parameter.source_name, header_value)
            headers.append((parameter.source_name, header_value))
    if "{" in path or "}" in path:
        raise ArgumentValidationError("Not all path parameters were resolved")

    json_body: object | None = None
    form_body: tuple[tuple[str, str], ...] | None = None
    multipart_body: tuple[MultipartPart, ...] | None = None
    body = mapping.body
    if body and body.tool_field in arguments:
        raw_body = arguments[body.tool_field]
        if body.media_type == "application/json":
            json_body = raw_body
            headers.append(("Content-Type", "application/json"))
        elif body.media_type == "application/x-www-form-urlencoded":
            form_body = _form_fields(raw_body)
            headers.append(("Content-Type", "application/x-www-form-urlencoded"))
        else:
            multipart_body = _multipart_parts(tool, raw_body)
    elif body and body.required:
        raise ArgumentValidationError(f"Missing required request body field {body.tool_field!r}")

    _apply_auth(headers, query, auth)
    return BuiltRequest(
        method=mapping.method.value,
        url=policy.resolve(mapping.server_ref, path),
        headers=tuple(headers),
        query=tuple(query),
        json_body=json_body,
        form_body=form_body,
        multipart_body=multipart_body,
    )
