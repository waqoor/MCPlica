from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import fsum
from typing import Literal, cast

from mcp_contracts.json_types import JsonObject
from pydantic import BaseModel

from app.core.exceptions import AIAnalysisError


@dataclass(frozen=True, slots=True)
class StructuredAttempt:
    ordinal: int
    outcome: Literal["accepted", "rejected", "transport_error"]
    model: str
    usage: JsonObject | None
    cost: JsonObject | None
    latency_ms: int


def _aggregate_json(values: list[JsonObject]) -> JsonObject:
    result: JsonObject = {}
    for key in sorted({key for value in values for key in value}):
        items = [value[key] for value in values if key in value]
        numbers = [
            item for item in items if isinstance(item, int | float) and not isinstance(item, bool)
        ]
        mappings = [cast(JsonObject, item) for item in items if isinstance(item, dict)]
        if len(numbers) == len(items):
            result[key] = (
                sum(cast(list[int], numbers))
                if all(isinstance(item, int) for item in numbers)
                else fsum(float(item) for item in numbers)
            )
        elif len(mappings) == len(items):
            result[key] = _aggregate_json(mappings)
    return result


def _status(values: list[JsonObject | None]) -> str:
    known = sum(value is not None for value in values)
    if known == len(values) and values:
        return "complete"
    if known:
        return "partial"
    return "unavailable"


def structured_usage_evidence(attempts: tuple[StructuredAttempt, ...]) -> JsonObject:
    values = [attempt.usage for attempt in attempts]
    result = _aggregate_json([value for value in values if value is not None])
    result.update(
        {
            "accounting_status": _status(values),
            "attempts": [
                {
                    "ordinal": attempt.ordinal,
                    "outcome": attempt.outcome,
                    "model": attempt.model,
                    "usage": attempt.usage,
                    "latency_ms": attempt.latency_ms,
                }
                for attempt in attempts
            ],
        }
    )
    return result


def structured_cost_evidence(attempts: tuple[StructuredAttempt, ...]) -> JsonObject:
    values = [attempt.cost for attempt in attempts]
    result = _aggregate_json([value for value in values if value is not None])
    result.update(
        {
            "accounting_status": _status(values),
            "attempts": [
                {
                    "ordinal": attempt.ordinal,
                    "outcome": attempt.outcome,
                    "model": attempt.model,
                    "cost": attempt.cost,
                    "latency_ms": attempt.latency_ms,
                }
                for attempt in attempts
            ],
        }
    )
    return result


def _raw_attempts(value: JsonObject | None, field: Literal["usage", "cost"]) -> list[JsonObject]:
    if value is None:
        return []
    attempts = value.get("attempts")
    if isinstance(attempts, list):
        return [cast(JsonObject, item) for item in attempts if isinstance(item, dict)]
    return [
        {
            "ordinal": 1,
            "outcome": "accepted",
            "model": "legacy",
            field: value,
            "latency_ms": 0,
        }
    ]


def merge_structured_evidence(
    previous: JsonObject | None,
    current: JsonObject | None,
    *,
    field: Literal["usage", "cost"],
) -> JsonObject | None:
    raw = [*_raw_attempts(previous, field), *_raw_attempts(current, field)]
    if not raw:
        return None
    attempts: list[StructuredAttempt] = []
    for ordinal, item in enumerate(raw, start=1):
        value = item.get(field)
        raw_outcome = item.get("outcome", "accepted")
        outcome = (
            raw_outcome
            if raw_outcome in {"accepted", "rejected", "transport_error"}
            else "accepted"
        )
        raw_latency = item.get("latency_ms")
        attempts.append(
            StructuredAttempt(
                ordinal=ordinal,
                outcome=cast(
                    Literal["accepted", "rejected", "transport_error"],
                    outcome,
                ),
                model=str(item.get("model") or "unknown"),
                usage=(
                    cast(JsonObject, value)
                    if field == "usage" and isinstance(value, dict)
                    else None
                ),
                cost=(
                    cast(JsonObject, value) if field == "cost" and isinstance(value, dict) else None
                ),
                latency_ms=(
                    raw_latency
                    if isinstance(raw_latency, int) and not isinstance(raw_latency, bool)
                    else 0
                ),
            )
        )
    packed = tuple(attempts)
    return (
        structured_usage_evidence(packed) if field == "usage" else structured_cost_evidence(packed)
    )


def unavailable_structured_evidence(*, field: Literal["usage", "cost"]) -> JsonObject:
    attempt = StructuredAttempt(
        ordinal=1,
        outcome="transport_error",
        model="unknown",
        usage=None,
        cost=None,
        latency_ms=0,
    )
    return (
        structured_usage_evidence((attempt,))
        if field == "usage"
        else structured_cost_evidence((attempt,))
    )


@dataclass(frozen=True, slots=True)
class StructuredGeneration[ResponseModel: BaseModel]:
    value: ResponseModel
    model: str
    response_sha256: str
    usage: JsonObject | None
    cost: JsonObject | None
    latency_ms: int
    attempts: tuple[StructuredAttempt, ...] = ()


class StructuredGenerationError(AIAnalysisError):
    def __init__(
        self,
        message: str,
        *,
        attempts: tuple[StructuredAttempt, ...],
    ) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.usage = structured_usage_evidence(attempts)
        self.cost = structured_cost_evidence(attempts)
        self.latency_ms = sum(attempt.latency_ms for attempt in attempts)


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
