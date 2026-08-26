import hashlib
import json
from typing import cast

from mcp_contracts.json_types import JsonObject
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

_MAX_REQUEST_BYTES = 1_000_000
_EMBEDDING_DIMENSIONS = 8


def _usage(*, prompt_tokens: int, completion_tokens: int = 0) -> dict[str, int | float]:
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost": 0.0,
    }


async def _json_body(request: Request) -> JsonObject | None:
    body = await request.body()
    if len(body) > _MAX_REQUEST_BYTES:
        return None
    try:
        value = cast(object, json.loads(body))
    except (TypeError, ValueError):
        return None
    return cast(JsonObject, value) if isinstance(value, dict) else None


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "mock-openrouter"})


async def models(_: Request) -> JSONResponse:
    return JSONResponse(
        {
            "data": [
                {
                    "id": "mcplica-fixture/analysis",
                    "name": "MCPlica deterministic analysis fixture",
                    "supported_parameters": ["structured_outputs"],
                    "architecture": {
                        "input_modalities": ["text"],
                        "output_modalities": ["text"],
                    },
                },
                {
                    "id": "mcplica-fixture/validation",
                    "name": "MCPlica deterministic validation fixture",
                    "supported_parameters": ["structured_outputs"],
                    "architecture": {
                        "input_modalities": ["text"],
                        "output_modalities": ["text"],
                    },
                },
                {
                    "id": "mcplica-fixture/embedding",
                    "name": "MCPlica deterministic embedding fixture",
                    "supported_parameters": [],
                    "architecture": {
                        "input_modalities": ["text"],
                        "output_modalities": ["embedding"],
                    },
                },
            ]
        }
    )


def _vector(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [round((digest[index] + 1) / 256, 8) for index in range(_EMBEDDING_DIMENSIONS)]


async def embeddings(request: Request) -> JSONResponse:
    payload = await _json_body(request)
    if payload is None:
        return JSONResponse({"error": "invalid_request"}, status_code=400)
    model = payload.get("model")
    raw_inputs_value = payload.get("input")
    if not isinstance(model, str) or not isinstance(raw_inputs_value, list):
        return JSONResponse({"error": "invalid_embedding_request"}, status_code=400)
    raw_inputs = cast(list[object], raw_inputs_value)
    inputs = [item for item in raw_inputs if isinstance(item, str)]
    if len(inputs) != len(raw_inputs) or not inputs:
        return JSONResponse({"error": "invalid_embedding_input"}, status_code=400)
    return JSONResponse(
        {
            "model": model,
            "data": [
                {"object": "embedding", "index": index, "embedding": _vector(text)}
                for index, text in enumerate(inputs)
            ],
            "usage": _usage(prompt_tokens=sum(max(1, len(text) // 4) for text in inputs)),
        }
    )


def _last_user_context(payload: JsonObject) -> JsonObject | None:
    raw_messages = payload.get("messages")
    if not isinstance(raw_messages, list):
        return None
    for raw in reversed(cast(list[object], raw_messages)):
        if not isinstance(raw, dict):
            continue
        message = cast(dict[str, object], raw)
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            return None
        try:
            decoded = cast(object, json.loads(content))
        except (TypeError, ValueError):
            return None
        return cast(JsonObject, decoded) if isinstance(decoded, dict) else None
    return None


async def chat_completions(request: Request) -> JSONResponse:
    payload = await _json_body(request)
    if payload is None:
        return JSONResponse({"error": "invalid_request"}, status_code=400)
    model = payload.get("model")
    response_format_value = payload.get("response_format")
    if not isinstance(model, str) or not isinstance(response_format_value, dict):
        return JSONResponse({"error": "invalid_structured_request"}, status_code=400)
    response_format = cast(dict[str, object], response_format_value)
    json_schema = response_format.get("json_schema")
    schema_name = (
        cast(dict[str, object], json_schema).get("name") if isinstance(json_schema, dict) else None
    )
    context = _last_user_context(payload)
    if context is None:
        return JSONResponse({"error": "missing_context"}, status_code=400)

    if schema_name == "operation_enrichment_v1":
        facts_value = context.get("authoritative_source_facts")
        if not isinstance(facts_value, dict):
            return JSONResponse({"error": "missing_operation_key"}, status_code=400)
        facts = cast(dict[str, object], facts_value)
        if not isinstance(facts.get("operation_key"), str):
            return JSONResponse({"error": "missing_operation_key"}, status_code=400)
        operation_key = cast(str, facts["operation_key"])
        operation_id = facts.get("operation_id")
        title_source = operation_id if isinstance(operation_id, str) else operation_key
        excerpts = context.get("untrusted_documentation_excerpts")
        chunk_ids: list[str] = []
        if isinstance(excerpts, list):
            for raw_excerpt in cast(list[object], excerpts):
                if not isinstance(raw_excerpt, dict):
                    continue
                chunk_id = cast(dict[str, object], raw_excerpt).get("chunk_id")
                if isinstance(chunk_id, str):
                    chunk_ids.append(chunk_id)
                if len(chunk_ids) == 20:
                    break
        content: dict[str, object] = {
            "operation_key": operation_key,
            "title": f"Enriched {title_source}",
            "description": (
                "Deterministic integration enrichment grounded in supplied source facts."
            ),
            "category": "integration",
            "keywords": ["mcplica", "integration"],
            "documentation_chunk_ids": chunk_ids,
            "relationship_hints": [],
            "confidence": 0.99,
            "warnings": [],
        }
    elif schema_name == "semantic_review_v1":
        content = {"findings": []}
    else:
        return JSONResponse({"error": "unsupported_schema"}, status_code=400)

    serialized = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return JSONResponse(
        {
            "id": "fixture-completion",
            "model": model,
            "choices": [{"message": {"role": "assistant", "content": serialized}}],
            "usage": _usage(
                prompt_tokens=max(1, len(json.dumps(context)) // 4),
                completion_tokens=max(1, len(serialized) // 4),
            ),
        }
    )


routes = [
    Route("/healthz", health, methods=["GET"]),
    Route("/api/v1/models", models, methods=["GET"]),
    Route("/api/v1/embeddings", embeddings, methods=["POST"]),
    Route("/api/v1/chat/completions", chat_completions, methods=["POST"]),
]

app = Starlette(routes=routes)
