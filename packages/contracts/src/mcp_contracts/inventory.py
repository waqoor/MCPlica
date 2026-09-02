from typing import Annotated, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

from .canonical import HttpMethod, ParameterLocation, SecuritySchemeType
from .json_types import JsonObject
from .path_template import path_parameter_names


class InventoryServer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")
    url: AnyHttpUrl
    description: str | None = None


class InventorySecurityScheme(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: SecuritySchemeType
    scheme: str | None = None
    location: Literal["header", "query", "cookie"] | None = None
    name: str | None = None
    token_url: AnyHttpUrl | None = None
    scopes: list[str] = Field(default_factory=lambda: list[str]())

    @model_validator(mode="after")
    def validate_shape(self) -> "InventorySecurityScheme":
        if self.type is SecuritySchemeType.API_KEY and (not self.location or not self.name):
            raise ValueError("api_key security requires location and name")
        if self.type is SecuritySchemeType.OAUTH2_CLIENT_CREDENTIALS and not self.token_url:
            raise ValueError("oauth2_client_credentials security requires token_url")
        if self.type is SecuritySchemeType.STATIC_HEADERS and not self.name:
            raise ValueError("static_headers security requires name")
        return self


class InventoryParameter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    name: str = Field(min_length=1)
    location: ParameterLocation = Field(alias="in")
    required: bool = False
    schema_: JsonObject = Field(alias="schema")
    description: str | None = None
    style: str | None = None
    explode: bool | None = None
    allow_reserved: bool = False

    @model_validator(mode="after")
    def path_parameter_is_required(self) -> "InventoryParameter":
        if self.location is ParameterLocation.PATH and not self.required:
            raise ValueError("path parameters must be required")
        return self


class InventoryRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    content_type: str = "application/json"
    required: bool = False
    description: str | None = None
    schema_: JsonObject = Field(alias="schema")


class InventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    content_type: str | None = None
    description: str | None = None
    schema_: JsonObject | None = Field(default=None, alias="schema")

    @model_validator(mode="after")
    def content_and_schema_are_paired(self) -> "InventoryResponse":
        if (self.content_type is None) != (self.schema_ is None):
            raise ValueError("response content_type and schema must be provided together")
        return self


SecurityRequirement = Annotated[dict[str, list[str]], Field(min_length=0)]


class InventoryOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: str | None = Field(default=None, min_length=1)
    method: HttpMethod
    path: str = Field(pattern=r"^/")
    server_id: str | None = None
    summary: str | None = None
    description: str | None = None
    parameters: list[InventoryParameter] = Field(default_factory=lambda: list[InventoryParameter]())
    request_body: InventoryRequestBody | None = None
    responses: dict[str, InventoryResponse] = Field(min_length=1)
    security: list[SecurityRequirement] = Field(default_factory=lambda: list[SecurityRequirement]())
    tags: list[str] = Field(default_factory=lambda: list[str]())

    @model_validator(mode="after")
    def validate_path_parameters(self) -> "InventoryOperation":
        placeholders = set(path_parameter_names(self.path))
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


class ApiInventory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_: Literal["api-inventory/v1"] = Field(alias="schema")
    name: str = Field(min_length=1, max_length=200)
    version: str | None = None
    description: str | None = None
    servers: list[InventoryServer] = Field(default_factory=lambda: list[InventoryServer]())
    security_schemes: dict[str, InventorySecurityScheme] = Field(
        default_factory=lambda: dict[str, InventorySecurityScheme]()
    )
    schemas: dict[str, JsonObject] = Field(default_factory=lambda: dict[str, JsonObject]())
    operations: list[InventoryOperation] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> "ApiInventory":
        server_ids = [server.id for server in self.servers]
        if len(server_ids) != len(set(server_ids)):
            raise ValueError("server IDs must be unique")
        operation_ids = [item.operation_id for item in self.operations if item.operation_id]
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("operation_id values must be unique")
        known_servers = set(server_ids)
        known_security = set(self.security_schemes)
        for operation in self.operations:
            if operation.server_id and operation.server_id not in known_servers:
                raise ValueError(
                    f"operation {operation.operation_id or operation.path!r} references "
                    "an unknown server"
                )
            for requirement in operation.security:
                unknown = set(requirement) - known_security
                if unknown:
                    raise ValueError(
                        "operation references unknown security schemes: "
                        + ", ".join(sorted(unknown))
                    )
        return self
