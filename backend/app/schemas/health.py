from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    service: Literal["mcplica-api"]


class ReadinessDependenciesRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    postgres: bool
    redis: bool
    artifact_storage: bool
    build_queue: bool
    milvus: bool
    openrouter: bool


class ReadinessRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    dependencies: ReadinessDependenciesRead
