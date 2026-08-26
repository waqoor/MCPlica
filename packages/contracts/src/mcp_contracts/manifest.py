from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ParameterTarget(StrEnum):
    PATH = "path"
    QUERY = "query"
    HEADER = "header"


class ServerDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    url: str
    description: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url_scheme(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("server URL must use http or https")
        return value.rstrip("/")


class AuthProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["none", "bearer", "api_key", "basic"]
    secret_env: str | None = None
    username_env: str | None = None
    password_env: str | None = None
    location: Literal["header", "query"] | None = None
    name: str | None = None
    prefix: str | None = None


class ParameterMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_field: str
    source_name: str
    target: ParameterTarget
    required: bool = False


class RequestBodyMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_field: str = "body"
    media_type: Literal["application/json", "application/x-www-form-urlencoded"] = "application/json"
    required: bool = False


class RequestMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    server_ref: str
    method: HttpMethod
    path: str
    parameters: list[ParameterMapping] = Field(default_factory=list)
    body: RequestBodyMapping | None = None


class MCPTool(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    operation_key: str
    request_mapping: RequestMapping
    security_profile_ref: str | None = None
    timeout_ms: int = Field(default=30_000, ge=100, le=300_000)
    max_response_bytes: int = Field(default=2_000_000, ge=1_024, le=50_000_000)
    enabled: bool = True
    provenance: dict[str, Any] = Field(default_factory=dict)


class MCPResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uri: str
    name: str
    description: str | None = None
    mime_type: str = "text/markdown"
    content: str


class RuntimeSecurity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inbound_auth_mode: Literal["static_bearer", "oidc", "none"] = "static_bearer"
    allow_insecure_none_only_in_development: bool = True


class ManifestProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    slug: str


class BuildMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_id: str
    source_digest: str
    created_at: str
    compiler_version: str


class MCPManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["mcp-manifest/v1"] = "mcp-manifest/v1"
    manifest_id: str
    project: ManifestProject
    runtime_compatibility: str = ">=0.1,<1.0"
    servers: list[ServerDefinition]
    auth_profiles: list[AuthProfile] = Field(default_factory=list)
    tools: list[MCPTool]
    resources: list[MCPResource] = Field(default_factory=list)
    security: RuntimeSecurity = Field(default_factory=RuntimeSecurity)
    build: BuildMetadata

    def enabled_tools(self) -> list[MCPTool]:
        return [tool for tool in self.tools if tool.enabled]
