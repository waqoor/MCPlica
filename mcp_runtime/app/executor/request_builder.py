from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from mcp_contracts import MCPTool, ServerDefinition
from mcp_contracts.manifest import ParameterTarget

from app.auth.upstream import AuthInjection
from app.security.url_policy import UpstreamUrlPolicy


@dataclass
class BuiltRequest:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    query: dict[str, Any] = field(default_factory=dict)
    json_body: Any | None = None
    form_body: dict[str, Any] | None = None


def build_request(
    tool: MCPTool,
    arguments: dict[str, Any],
    server: ServerDefinition,
    auth: AuthInjection,
) -> BuiltRequest:
    path = tool.request_mapping.path
    query: dict[str, Any] = dict(auth.query)
    headers: dict[str, str] = {**auth.headers, "Accept": "application/json, text/plain;q=0.9, */*;q=0.1"}

    for mapping in tool.request_mapping.parameters:
        if mapping.required and mapping.tool_field not in arguments:
            raise ValueError(f"Missing required field {mapping.tool_field}")
        if mapping.tool_field not in arguments:
            continue
        value = arguments[mapping.tool_field]
        if mapping.target == ParameterTarget.PATH:
            placeholder = "{" + mapping.source_name + "}"
            if placeholder not in path:
                raise ValueError(f"Manifest path missing placeholder {placeholder}")
            path = path.replace(placeholder, quote(str(value), safe=""))
        elif mapping.target == ParameterTarget.QUERY:
            query[mapping.source_name] = value
        elif mapping.target == ParameterTarget.HEADER:
            lowered = mapping.source_name.lower()
            if lowered in {"authorization", "proxy-authorization", "host", "cookie", "set-cookie"}:
                raise ValueError(f"Forbidden caller-controlled header: {mapping.source_name}")
            headers[mapping.source_name] = str(value)

    if "{" in path or "}" in path:
        raise ValueError("Not all path parameters were resolved")

    json_body = None
    form_body = None
    body = tool.request_mapping.body
    if body and body.tool_field in arguments:
        if body.media_type == "application/json":
            json_body = arguments[body.tool_field]
        else:
            raw = arguments[body.tool_field]
            if not isinstance(raw, dict):
                raise ValueError("Form body must be an object")
            form_body = raw
    elif body and body.required:
        raise ValueError(f"Missing required request body field {body.tool_field}")

    policy = UpstreamUrlPolicy(server.url)
    return BuiltRequest(
        method=tool.request_mapping.method.value,
        url=policy.resolve(path),
        headers=headers,
        query=query,
        json_body=json_body,
        form_body=form_body,
    )
