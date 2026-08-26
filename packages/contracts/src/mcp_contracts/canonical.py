from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ParameterLocation(StrEnum):
    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"


class CanonicalServer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    url: str
    description: str | None = None


class CanonicalParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    location: ParameterLocation
    required: bool = False
    schema_: dict[str, Any] = Field(default_factory=dict, alias="schema")
    description: str | None = None
    style: str | None = None
    explode: bool | None = None


class CanonicalRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required: bool = False
    media_type: str = "application/json"
    schema_: dict[str, Any] = Field(default_factory=dict, alias="schema")


class CanonicalOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    operation_id: str | None = None
    method: str
    path: str
    title: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    parameters: list[CanonicalParameter] = Field(default_factory=list)
    request_body: CanonicalRequestBody | None = None
    response_schema: dict[str, Any] | None = None
    security_scheme_names: list[str] = Field(default_factory=list)
    source_pointer: str


class CanonicalApi(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_format: str
    title: str
    version: str | None = None
    servers: list[CanonicalServer]
    operations: list[CanonicalOperation]
    security_schemes: dict[str, dict[str, Any]] = Field(default_factory=dict)
