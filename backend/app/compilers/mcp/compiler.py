import hashlib
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from mcp_contracts import (
    AuthProfile,
    BuildMetadata,
    CanonicalApi,
    ManifestProject,
    MCPManifest,
    MCPTool,
    ParameterMapping,
    RequestBodyMapping,
    RequestMapping,
    RuntimeSecurity,
    ServerDefinition,
)
from mcp_contracts.canonical import ParameterLocation
from mcp_contracts.manifest import HttpMethod, ParameterTarget

from app.core.exceptions import ValidationError

NON_ALNUM = re.compile(r"[^a-zA-Z0-9_]+")
MULTI_UNDERSCORE = re.compile(r"_+")


def _snake(value: str) -> str:
    value = re.sub(r"(?<!^)(?=[A-Z])", "_", value)
    value = NON_ALNUM.sub("_", value).strip("_").lower()
    value = MULTI_UNDERSCORE.sub("_", value)
    if not value:
        return "operation"
    if value[0].isdigit():
        value = f"op_{value}"
    return value[:96]


def _tool_name(operation_id: str | None, method: str, path: str, operation_key: str) -> str:
    if operation_id:
        candidate = _snake(operation_id)
    else:
        path_words = re.sub(r"[{}]", "", path).strip("/").replace("/", "_")
        candidate = _snake(f"{method}_{path_words}")
    return candidate or f"operation_{operation_key[-8:]}"


def _auth_profiles(api: CanonicalApi) -> tuple[list[AuthProfile], dict[str, str]]:
    profiles: list[AuthProfile] = []
    refs: dict[str, str] = {}
    for name, scheme in sorted(api.security_schemes.items()):
        scheme_type = scheme.get("type")
        profile_id = f"auth_{_snake(name)}"
        if scheme_type == "http" and str(scheme.get("scheme", "")).lower() == "bearer":
            profiles.append(AuthProfile(id=profile_id, type="bearer", secret_env="MCP_UPSTREAM_BEARER_TOKEN"))
            refs[name] = profile_id
        elif scheme_type == "http" and str(scheme.get("scheme", "")).lower() == "basic":
            profiles.append(
                AuthProfile(
                    id=profile_id,
                    type="basic",
                    username_env="MCP_UPSTREAM_BASIC_USERNAME",
                    password_env="MCP_UPSTREAM_BASIC_PASSWORD",
                )
            )
            refs[name] = profile_id
        elif scheme_type == "apiKey" and scheme.get("in") in {"header", "query"}:
            profiles.append(
                AuthProfile(
                    id=profile_id,
                    type="api_key",
                    secret_env="MCP_UPSTREAM_API_KEY",
                    location=scheme["in"],
                    name=str(scheme["name"]),
                )
            )
            refs[name] = profile_id
        else:
            # Starter compiler fails closed instead of inventing OAuth/custom behavior.
            refs[name] = "__unsupported__"
    return profiles, refs


def compile_manifest(
    api: CanonicalApi,
    *,
    project_id: str,
    project_name: str,
    project_slug: str,
    source_digest: str,
    build_id: str | None = None,
) -> MCPManifest:
    build_id = build_id or str(uuid4())
    profiles, profile_refs = _auth_profiles(api)
    server_defs = [
        ServerDefinition(id=server.key, url=server.url, description=server.description)
        for server in api.servers
    ]
    used_names: dict[str, str] = {}
    tools: list[MCPTool] = []

    for operation in api.operations:
        if any(profile_refs.get(name) == "__unsupported__" for name in operation.security_scheme_names):
            raise ValidationError(
                f"{operation.method} {operation.path} uses unsupported security scheme"
            )

        base_name = _tool_name(
            operation.operation_id, operation.method, operation.path, operation.operation_key
        )
        name = base_name
        if name in used_names and used_names[name] != operation.operation_key:
            name = f"{base_name}_{operation.operation_key[-8:]}"
        used_names[name] = operation.operation_key

        properties: dict[str, Any] = {}
        required: list[str] = []
        mappings: list[ParameterMapping] = []
        for parameter in operation.parameters:
            if parameter.location == ParameterLocation.COOKIE:
                raise ValidationError(
                    f"{operation.method} {operation.path}: cookie parameters are not executable in starter compiler"
                )
            field_name = parameter.name
            if field_name in properties:
                field_name = f"{parameter.location.value}_{field_name}"
            schema = dict(parameter.schema_)
            if parameter.description and "description" not in schema:
                schema["description"] = parameter.description
            properties[field_name] = schema or {"type": "string"}
            if parameter.required:
                required.append(field_name)
            target = ParameterTarget(parameter.location.value)
            mappings.append(
                ParameterMapping(
                    tool_field=field_name,
                    source_name=parameter.name,
                    target=target,
                    required=parameter.required,
                )
            )

        body_mapping = None
        if operation.request_body:
            properties["body"] = operation.request_body.schema_
            if operation.request_body.required:
                required.append("body")
            body_mapping = RequestBodyMapping(
                tool_field="body",
                media_type=operation.request_body.media_type,
                required=operation.request_body.required,
            )

        input_schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }
        if required:
            input_schema["required"] = sorted(set(required))

        auth_ref = None
        for scheme_name in operation.security_scheme_names:
            if scheme_name in profile_refs:
                auth_ref = profile_refs[scheme_name]
                break

        description = operation.description or operation.title
        tools.append(
            MCPTool(
                name=name,
                title=operation.title,
                description=description,
                input_schema=input_schema,
                output_schema=operation.response_schema,
                operation_key=operation.operation_key,
                request_mapping=RequestMapping(
                    server_ref=server_defs[0].id,
                    method=HttpMethod(operation.method),
                    path=operation.path,
                    parameters=mappings,
                    body=body_mapping,
                ),
                security_profile_ref=auth_ref,
                provenance={"source_pointer": operation.source_pointer},
            )
        )

    manifest_seed = f"{project_id}:{build_id}:{source_digest}".encode()
    manifest_id = hashlib.sha256(manifest_seed).hexdigest()
    return MCPManifest(
        manifest_id=manifest_id,
        project=ManifestProject(id=project_id, name=project_name, slug=project_slug),
        servers=server_defs,
        auth_profiles=profiles,
        tools=tools,
        security=RuntimeSecurity(inbound_auth_mode="static_bearer"),
        build=BuildMetadata(
            build_id=build_id,
            source_digest=source_digest,
            created_at=datetime.now(UTC).isoformat(),
            compiler_version="0.1.0",
        ),
    )
