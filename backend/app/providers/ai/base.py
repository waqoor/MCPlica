from abc import ABC, abstractmethod
from dataclasses import dataclass

from mcp_contracts.json_types import JsonObject
from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class StructuredGeneration[ResponseModel: BaseModel]:
    value: ResponseModel
    model: str
    response_sha256: str
    usage: JsonObject | None
    cost: JsonObject | None
    latency_ms: int


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    model: str
    dimensions: int
    usage: JsonObject | None


@dataclass(frozen=True, slots=True)
class AIModelInfo:
    id: str
    name: str
    supported_parameters: frozenset[str]
    input_modalities: frozenset[str]
    output_modalities: frozenset[str]
    raw: JsonObject


class AIProvider(ABC):
    @abstractmethod
    async def structured_generate[ResponseModel: BaseModel](
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        response_model: type[ResponseModel],
        schema_name: str,
    ) -> StructuredGeneration[ResponseModel]: ...

    @abstractmethod
    async def embed(self, *, model: str, texts: list[str]) -> EmbeddingBatch: ...

    @abstractmethod
    async def list_models(self) -> list[AIModelInfo]: ...
