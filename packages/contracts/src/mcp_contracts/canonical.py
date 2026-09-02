from enum import StrEnum
from typing import Literal, cast
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

from .json_types import JsonObject, JsonValue
from .path_template import path_parameter_names


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    TRACE = "TRACE"


class ParameterLocation(StrEnum):
    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"


class SecuritySchemeType(StrEnum):
    HTTP_BEARER = "http_bearer"
    HTTP_BASIC = "http_basic"
    API_KEY = "api_key"
    OAUTH2_CLIENT_CREDENTIALS = "oauth2_client_credentials"
    STATIC_HEADERS = "static_headers"
    UNSUPPORTED = "unsupported"


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_version_id: UUID
    pointer: str = Field(min_length=1)


class SchemaTransformationProvenance(BaseModel):
    """An executable schema rewrite applied while producing the canonical model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_pointer: str = Field(min_length=1)
    transformation: Literal[
        "nullable",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "example",
    ]


class SchemaDialectProvenance(BaseModel):
    """The source and executable JSON Schema dialects for a canonical API."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(min_length=1)
    target: Literal["https://json-schema.org/draft/2020-12/schema"]
    transformations: list[SchemaTransformationProvenance] = Field(
        default_factory=lambda: list[SchemaTransformationProvenance]()
    )


class CanonicalProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_version_ids: list[UUID] = Field(min_length=1)
    source_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    schema_dialect: SchemaDialectProvenance | None = None


class SemanticProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    model: str
    prompt_template_id: str
    prompt_template_version: str
    context_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    retrieved_chunk_ids: list[str] = Field(default_factory=list)


class OperationSemanticMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    category: str | None = None
    keywords: list[str] = Field(default_factory=list)
    documentation_chunk_ids: list[str] = Field(default_factory=list)
    relationship_hints: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    provenance: SemanticProvenance | None = None


class CanonicalServer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1, max_length=120)
    url: AnyHttpUrl
    description: str | None = None
    source_ref: SourceRef

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        return AnyHttpUrl(str(value).rstrip("/"))


class CanonicalSecurityScheme(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: SecuritySchemeType
    scheme: str | None = None
    location: Literal["header", "query", "cookie"] | None = None
    name: str | None = None
    token_url: AnyHttpUrl | None = None
    scopes: list[str] = Field(default_factory=list)
    source_ref: SourceRef

    @model_validator(mode="after")
    def validate_shape(self) -> "CanonicalSecurityScheme":
        if self.type is SecuritySchemeType.API_KEY and (not self.location or not self.name):
            raise ValueError("API-key security schemes require location and name")
        if self.type is SecuritySchemeType.OAUTH2_CLIENT_CREDENTIALS and not self.token_url:
            raise ValueError("OAuth client-credentials schemes require token_url")
        return self


class CanonicalSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    key: str
    schema_: JsonObject = Field(alias="schema")
    source_ref: SourceRef


class CanonicalParameter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    name: str = Field(min_length=1)
    location: ParameterLocation
    required: bool = False
    schema_: JsonObject = Field(alias="schema")
    description: str | None = None
    style: str | None = None
    explode: bool | None = None
    allow_reserved: bool = False
    source_ref: SourceRef

    @model_validator(mode="after")
    def path_parameters_are_required(self) -> "CanonicalParameter":
        if self.location is ParameterLocation.PATH and not self.required:
            raise ValueError("path parameters must be required")
        return self


class CanonicalMediaType(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    media_type: str
    schema_: JsonObject = Field(alias="schema")
    examples: list[JsonValue] = Field(default_factory=lambda: list[JsonValue]())
    source_ref: SourceRef


class CanonicalRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    required: bool = False
    description: str | None = None
    content: list[CanonicalMediaType] = Field(min_length=1)
    source_ref: SourceRef


class CanonicalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status_code: str
    description: str | None = None
    content: list[CanonicalMediaType] = Field(default_factory=lambda: list[CanonicalMediaType]())
    source_ref: SourceRef


class CanonicalSecurityRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scheme_scopes: dict[str, list[str]] = Field(default_factory=lambda: dict[str, list[str]]())
    source_ref: SourceRef


class OperationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: SourceRef
    executable_fields: dict[str, SourceRef] = Field(default_factory=lambda: dict[str, SourceRef]())


class CanonicalOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=160)
    source_operation_id: str | None = None
    tool_name_seed: str = Field(min_length=1, max_length=128)
    method: HttpMethod
    path_template: str = Field(pattern=r"^/")
    server_ref: str | None = None
    server_candidates: list[str] = Field(min_length=1)
    summary: str | None = None
    description: str | None = None
    parameters: list[CanonicalParameter] = Field(default_factory=lambda: list[CanonicalParameter]())
    request_body: CanonicalRequestBody | None = None
    responses: list[CanonicalResponse] = Field(default_factory=lambda: list[CanonicalResponse]())
    security: list[CanonicalSecurityRequirement] = Field(
        default_factory=lambda: list[CanonicalSecurityRequirement]()
    )
    tags: list[str] = Field(default_factory=lambda: list[str]())
    semantic: OperationSemanticMetadata = Field(default_factory=OperationSemanticMetadata)
    provenance: OperationProvenance

    @model_validator(mode="before")
    @classmethod
    def restore_legacy_server_candidates(cls, value: object) -> object:
        """Read pre-routing v1 snapshots without changing their persisted hash."""
        if not isinstance(value, dict):
            return value
        operation = cast(dict[str, object], value)
        if "server_candidates" in operation:
            return operation
        server_ref = operation.get("server_ref")
        if not isinstance(server_ref, str) or not server_ref:
            raise ValueError(
                "legacy canonical operations without server_candidates require server_ref"
            )
        return {**operation, "server_candidates": [server_ref]}

    @model_validator(mode="after")
    def validate_path_parameters(self) -> "CanonicalOperation":
        placeholders = set(path_parameter_names(self.path_template))
        parameters = {
            parameter.name
            for parameter in self.parameters
            if parameter.location is ParameterLocation.PATH
        }
        if placeholders != parameters:
            missing = sorted(placeholders - parameters)
            extra = sorted(parameters - placeholders)
            raise ValueError(f"path parameter mismatch; missing={missing}, extra={extra}")
        return self


class DocumentationRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_version_id: UUID
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    title: str | None = None


class CanonicalApi(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["canonical-api/v1"] = "canonical-api/v1"
    project_id: UUID
    source_format: Literal["openapi-3.0", "openapi-3.1", "api-inventory/v1"]
    title: str
    version: str | None = None
    description: str | None = None
    servers: list[CanonicalServer] = Field(min_length=1)
    active_server_ref: str | None = None
    security_schemes: dict[str, CanonicalSecurityScheme] = Field(
        default_factory=lambda: dict[str, CanonicalSecurityScheme]()
    )
    schemas: dict[str, CanonicalSchema] = Field(
        default_factory=lambda: dict[str, CanonicalSchema]()
    )
    operations: list[CanonicalOperation] = Field(min_length=1)
    documentation_refs: list[DocumentationRef] = Field(
        default_factory=lambda: list[DocumentationRef]()
    )
    provenance: CanonicalProvenance

    @model_validator(mode="after")
    def validate_references_and_uniqueness(self) -> "CanonicalApi":
        server_keys = {server.key for server in self.servers}
        if len(server_keys) != len(self.servers):
            raise ValueError("canonical server keys must be unique")
        if self.active_server_ref is not None and self.active_server_ref not in server_keys:
            raise ValueError("active_server_ref references an unknown server")
        operation_keys = [operation.key for operation in self.operations]
        if len(set(operation_keys)) != len(operation_keys):
            raise ValueError("canonical operation keys must be unique")
        for operation in self.operations:
            unknown_candidates = set(operation.server_candidates) - server_keys
            if unknown_candidates:
                raise ValueError(
                    f"operation {operation.key} has unknown server candidates: "
                    + ", ".join(sorted(unknown_candidates))
                )
            if operation.server_ref is not None and operation.server_ref not in server_keys:
                raise ValueError(f"operation {operation.key} references an unknown server")
            if (
                operation.server_ref is not None
                and operation.server_ref not in operation.server_candidates
            ):
                raise ValueError(
                    f"operation {operation.key} selected a server outside its candidate set"
                )
            for requirement in operation.security:
                unknown = set(requirement.scheme_scopes) - set(self.security_schemes)
                if unknown:
                    raise ValueError(
                        f"operation {operation.key} references unknown security schemes: "
                        + ", ".join(sorted(unknown))
                    )
        return self
