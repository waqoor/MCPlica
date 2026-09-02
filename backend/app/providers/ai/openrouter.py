import hashlib
import json
import time
from typing import cast

from mcp_contracts.json_types import JsonObject, JsonValue
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from app.clients.ai import OpenRouterClient
from app.core.canonical_json import canonical_json_bytes
from app.core.exceptions import ClientResponseError
from app.observability import observe_openrouter_usage
from app.providers.ai.base import (
    AIModelInfo,
    AIProvider,
    EmbeddingBatch,
    StructuredAttempt,
    StructuredGeneration,
    StructuredGenerationError,
    structured_cost_evidence,
    structured_usage_evidence,
)


def _usage(payload: JsonObject) -> JsonObject | None:
    value = payload.get("usage")
    return cast(JsonObject, value) if isinstance(value, dict) else None


def _structured_content(payload: JsonObject) -> object:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenRouter response has no choices")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise ValueError("OpenRouter choice is malformed")
    message = choice.get("message")
    if not isinstance(message, dict) or "content" not in message:
        raise ValueError("OpenRouter choice message is malformed")
    raw_content = message["content"]
    if isinstance(raw_content, dict):
        return raw_content
    if not isinstance(raw_content, str):
        raise ValueError("OpenRouter structured content must be JSON text or an object")
    return cast(object, json.loads(raw_content))


def _string_values(value: JsonValue | None) -> frozenset[str]:
    if not isinstance(value, list):
        return frozenset()
    return frozenset(item for item in value if isinstance(item, str))


class OpenRouterProvider(AIProvider):
    def __init__(self, client: OpenRouterClient, *, structured_attempts: int = 2) -> None:
        self._client = client
        self._structured_attempts = structured_attempts

    async def structured_generate[ResponseModel: BaseModel](
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        response_model: type[ResponseModel],
        schema_name: str,
    ) -> StructuredGeneration[ResponseModel]:
        payload = {
            "model": model,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": response_model.model_json_schema(),
                },
            },
        }
        last_error: Exception | None = None
        attempts: list[StructuredAttempt] = []
        for ordinal in range(1, self._structured_attempts + 1):
            started = time.perf_counter()
            try:
                response = await self._client.chat_completion(payload)
            except Exception as exc:
                attempts.append(
                    StructuredAttempt(
                        ordinal=ordinal,
                        outcome="transport_error",
                        model=model,
                        usage=None,
                        cost=None,
                        latency_ms=round((time.perf_counter() - started) * 1000),
                    )
                )
                raise StructuredGenerationError(
                    "OpenRouter structured generation failed before accounting was available",
                    attempts=tuple(attempts),
                ) from exc
            latency_ms = round((time.perf_counter() - started) * 1000)
            usage = _usage(response)
            observe_openrouter_usage(usage)
            cost = {"cost": usage["cost"]} if usage and "cost" in usage else None
            resolved_model = str(response.get("model") or model)
            try:
                value = response_model.model_validate(_structured_content(response))
            except (
                KeyError,
                IndexError,
                TypeError,
                ValueError,
                PydanticValidationError,
            ) as exc:
                last_error = exc
                attempts.append(
                    StructuredAttempt(
                        ordinal=ordinal,
                        outcome="rejected",
                        model=resolved_model,
                        usage=usage,
                        cost=cost,
                        latency_ms=latency_ms,
                    )
                )
                continue
            serialized = canonical_json_bytes(value)
            attempts.append(
                StructuredAttempt(
                    ordinal=ordinal,
                    outcome="accepted",
                    model=resolved_model,
                    usage=usage,
                    cost=cost,
                    latency_ms=latency_ms,
                )
            )
            packed_attempts = tuple(attempts)
            return StructuredGeneration(
                value=value,
                model=resolved_model,
                response_sha256=hashlib.sha256(serialized).hexdigest(),
                usage=structured_usage_evidence(packed_attempts),
                cost=structured_cost_evidence(packed_attempts),
                latency_ms=sum(attempt.latency_ms for attempt in packed_attempts),
                attempts=packed_attempts,
            )
        raise StructuredGenerationError(
            "OpenRouter returned invalid structured output after bounded retries",
            attempts=tuple(attempts),
        ) from last_error

    async def embed(self, *, model: str, texts: list[str]) -> EmbeddingBatch:
        if not texts:
            raise ValueError("At least one text is required for embedding")
        response = await self._client.embeddings({"model": model, "input": texts})
        raw_data = response.get("data")
        if not isinstance(raw_data, list) or len(raw_data) != len(texts):
            raise ClientResponseError("OpenRouter embedding count does not match input count")
        vectors_by_index: list[list[float] | None] = [None] * len(texts)
        for item in cast(list[JsonValue], raw_data):
            if not isinstance(item, dict):
                raise ClientResponseError("OpenRouter returned malformed embeddings")
            raw_vector = item.get("embedding")
            if not isinstance(raw_vector, list):
                raise ClientResponseError("OpenRouter returned malformed embeddings")
            try:
                vector = [
                    float(value)
                    for value in cast(list[JsonValue], raw_vector)
                    if isinstance(value, int | float) and not isinstance(value, bool)
                ]
                if len(vector) != len(raw_vector):
                    raise ValueError("embedding contains a non-numeric value")
                raw_index = item.get("index")
                if not isinstance(raw_index, int) or isinstance(raw_index, bool):
                    raise ValueError("embedding index is not an integer")
                index = raw_index
            except (TypeError, ValueError) as exc:
                raise ClientResponseError("OpenRouter returned malformed embeddings") from exc
            if not vector:
                raise ClientResponseError("OpenRouter returned an empty embedding")
            if index < 0 or index >= len(texts) or vectors_by_index[index] is not None:
                raise ClientResponseError(
                    "OpenRouter returned invalid or duplicate embedding indexes"
                )
            vectors_by_index[index] = vector
        if any(vector is None for vector in vectors_by_index):
            raise ClientResponseError("OpenRouter returned incomplete embedding indexes")
        vectors = [vector for vector in vectors_by_index if vector is not None]
        dimensions = len(vectors[0])
        if any(len(vector) != dimensions for vector in vectors):
            raise ClientResponseError("OpenRouter returned inconsistent embedding dimensions")
        usage = _usage(response)
        observe_openrouter_usage(usage)
        return EmbeddingBatch(
            vectors=vectors,
            model=str(response.get("model") or model),
            dimensions=dimensions,
            usage=usage,
        )

    async def list_models(self) -> list[AIModelInfo]:
        result: list[AIModelInfo] = []
        for raw in await self._client.models():
            model_id = raw.get("id")
            if not isinstance(model_id, str) or not model_id:
                continue
            architecture = raw.get("architecture")
            architecture = cast(JsonObject, architecture) if isinstance(architecture, dict) else {}
            result.append(
                AIModelInfo(
                    id=model_id,
                    name=str(raw.get("name") or model_id),
                    supported_parameters=_string_values(raw.get("supported_parameters")),
                    input_modalities=_string_values(architecture.get("input_modalities")),
                    output_modalities=_string_values(architecture.get("output_modalities")),
                    raw=raw,
                )
            )
        return result
