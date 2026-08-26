import re
from enum import StrEnum
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

from .canonical import HttpMethod
from .json_types import JsonObject, JsonValue

_HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_FORBIDDEN_AUTH_HEADERS = {
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


class ParameterTarget(StrEnum):
    PATH = "path"
    QUERY = "query"
    HEADER = "header"


class ServerDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    url: AnyHttpUrl
    description: str | None = None

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        return AnyHttpUrl(str(value).rstrip("/"))


class AuthProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    type: Literal[
        "none",
        "bearer",
        "api_key",
        "basic",
        "oauth2_client_credentials",
        "static_header",
    ]
    credential_ref: str | None = None
    token_url: AnyHttpUrl | None = None
    scopes: list[str] = Field(default_factory=list)
    token_auth_method: Literal["client_secret_basic", "client_secret_post"] = "client_secret_basic"
    location: Literal["header", "query"] | None = None
    name: str | None = None
    prefix: str | None = None

    @model_validator(mode="after")
    def validate_auth_fields(self) -> "AuthProfile":
        required: dict[str, tuple[str, ...]] = {
            "api_key": ("location", "name"),
            "oauth2_client_credentials": ("token_url",),
            "static_header": ("name",),
        }
        missing = [field for field in required.get(self.type, ()) if getattr(self, field) is None]
        if self.type != "none" and not self.credential_ref:
            missing.append("credential_ref")
        if missing:
            raise ValueError(f"{self.type} auth profile is missing: {', '.join(missing)}")
        if self.type == "none" and self.credential_ref is not None:
            raise ValueError("none auth profile cannot reference credentials")
        if self.type != "oauth2_client_credentials" and (self.token_url or self.scopes):
            raise ValueError(f"{self.type} auth profile cannot contain OAuth configuration")
        if self.type != "api_key" and (self.location is not None or self.prefix is not None):
            raise ValueError(f"{self.type} auth profile cannot contain API-key configuration")
        if self.type not in {"api_key", "static_header"} and self.name is not None:
            raise ValueError(f"{self.type} auth profile cannot contain a header/query name")
        if self.credential_ref is not None and (
            len(self.credential_ref) > 200
            or any(character in self.credential_ref for character in "\r\n\x00")
        ):
            raise ValueError("auth profile credential reference is invalid")
        if self.name is not None:
            if not self.name or any(character in self.name for character in "\r\n\x00"):
                raise ValueError("auth profile name is invalid")
            if (self.location == "header" or self.type == "static_header") and (
                not _HEADER_NAME.fullmatch(self.name)
                or self.name.casefold() in _FORBIDDEN_AUTH_HEADERS
            ):
                raise ValueError("auth profile contains a forbidden header name")
        if self.prefix is not None and any(character in self.prefix for character in "\r\n\x00"):
            raise ValueError("API-key prefix contains forbidden characters")
        return self


class ParameterMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_field: str
    source_name: str
    target: ParameterTarget
    required: bool = False
    style: str | None = None
    explode: bool | None = None
    allow_reserved: bool = False


class MultipartFileMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    part_name: str
    content_field: str
    filename_field: str | None = None
    content_type_field: str | None = None
    default_filename: str = "upload.bin"
    default_content_type: str = "application/octet-stream"
    required: bool = False


class RequestBodyMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_field: str = "body"
    media_type: Literal[
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    ] = "application/json"
    required: bool = False
    multipart_files: list[MultipartFileMapping] = Field(default_factory=list[MultipartFileMapping])


class RequestMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    server_ref: str
    method: HttpMethod
    path: str = Field(pattern=r"^/")
    parameters: list[ParameterMapping] = Field(default_factory=list[ParameterMapping])
    body: RequestBodyMapping | None = None


class ResponseDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    status_code: str
    media_type: str | None = None
    schema_: JsonObject | None = Field(default=None, alias="schema")
    description: str | None = None


class MCPTool(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z_][a-z0-9_]{0,127}$")
    title: str
    description: str
    input_schema: JsonObject
    output_schema: JsonObject | None = None
    responses: list[ResponseDefinition] = Field(default_factory=list[ResponseDefinition])
    operation_key: str
    request_mapping: RequestMapping
    security_profile_ref: str | None = None
    timeout_ms: int = Field(default=30_000, ge=100, le=300_000)
    max_response_bytes: int = Field(default=2_000_000, ge=1_024, le=50_000_000)
    enabled: bool = True
    max_request_bytes: int = Field(default=10_000_000, ge=1_024, le=100_000_000)
    provenance: dict[str, JsonValue] = Field(default_factory=dict)


class MCPResource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    uri: str
    name: str
    description: str | None = None
    mime_type: str = "text/markdown"
    content: str
    provenance: dict[str, JsonValue] = Field(default_factory=dict)


class RuntimeSecurity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    inbound_auth_mode: Literal["static_bearer", "oidc", "none"] = "static_bearer"
    allowed_upstream_hosts: list[str] = Field(min_length=1)
    allow_insecure_none_only_in_development: bool = True
    default_timeout_ms: int = Field(default=30_000, ge=100, le=300_000)
    default_max_response_bytes: int = Field(
        default=2_000_000,
        ge=1_024,
        le=50_000_000,
    )


class ManifestProject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    slug: str


class BuildMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    build_id: str
    source_version_ids: list[str] = Field(min_length=1)
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    canonical_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: str
    compiler_version: str
    prompt_bundle_version: str | None = None
    analysis_model: str | None = None
    validation_model: str | None = None
    embedding_model: str | None = None


class MCPManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["mcp-manifest/v1"] = "mcp-manifest/v1"
    manifest_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    project: ManifestProject
    runtime_compatibility: str = ">=1.0,<2.0"
    servers: list[ServerDefinition] = Field(min_length=1)
    auth_profiles: list[AuthProfile] = Field(default_factory=list[AuthProfile])
    tools: list[MCPTool]
    resources: list[MCPResource] = Field(default_factory=list[MCPResource])
    security: RuntimeSecurity
    build: BuildMetadata

    @model_validator(mode="after")
    def validate_references(self) -> "MCPManifest":
        server_ids = [server.id for server in self.servers]
        auth_ids = [profile.id for profile in self.auth_profiles]
        tool_names = [tool.name for tool in self.tools]
        if len(set(server_ids)) != len(server_ids):
            raise ValueError("manifest server IDs must be unique")
        if len(set(auth_ids)) != len(auth_ids):
            raise ValueError("manifest auth profile IDs must be unique")
        if len(set(tool_names)) != len(tool_names):
            raise ValueError("manifest tool names must be unique")
        for tool in self.tools:
            if tool.request_mapping.server_ref not in server_ids:
                raise ValueError(f"tool {tool.name} references unknown server")
            if tool.security_profile_ref and tool.security_profile_ref not in auth_ids:
                raise ValueError(f"tool {tool.name} references unknown auth profile")
        return self

    def enabled_tools(self) -> list[MCPTool]:
        return [tool for tool in self.tools if tool.enabled]
