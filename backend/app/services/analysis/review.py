import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from mcp_contracts import CanonicalApi, MCPManifest

from app.clients.database import DatabaseClient
from app.core.exceptions import AIAnalysisError, MCPlicaError
from app.domain.analysis import SemanticReviewFinding, SemanticReviewResult
from app.prompts import SEMANTIC_REVIEW_PROMPT
from app.providers.ai.base import (
    AIProvider,
    StructuredGenerationError,
    merge_structured_evidence,
    unavailable_structured_evidence,
)
from app.repositories.builds import BuildAIRunRepository


class SemanticReviewService:
    def __init__(
        self,
        database: DatabaseClient,
        ai: AIProvider,
        ai_runs: BuildAIRunRepository,
    ) -> None:
        self._database = database
        self._ai = ai
        self._ai_runs = ai_runs

    async def review(
        self,
        *,
        build_id: UUID,
        canonical: CanonicalApi,
        manifest: MCPManifest,
        model: str,
        max_context_chars: int,
        admission_token: UUID,
        cancellation_check: Callable[[], Awaitable[None]] | None = None,
    ) -> list[SemanticReviewFinding]:
        contexts = _batched_contexts(canonical, manifest, max_context_chars)
        findings: list[SemanticReviewFinding] = []
        known_operations = {operation.key for operation in canonical.operations}
        for context in contexts:
            if cancellation_check is not None:
                await cancellation_check()
            context_sha256 = hashlib.sha256(context.encode()).hexdigest()
            run_key = f"semantic-review:{context_sha256[:32]}"
            async with self._database.session_scope() as session:
                existing = await self._ai_runs.get_by_run_key(
                    session,
                    build_id=build_id,
                    run_key=run_key,
                )
            if existing is not None and existing.status == "succeeded":
                invalid_code: str | None = None
                try:
                    if existing.response is None:
                        raise ValueError("missing response")
                    result = SemanticReviewResult.model_validate(existing.response)
                    unknown = _unknown_operations(result, known_operations)
                    if unknown:
                        invalid_code = "SEMANTIC_REVIEW_UNKNOWN_OPERATION"
                    else:
                        findings.extend(result.findings)
                        continue
                except (TypeError, ValueError):
                    invalid_code = "SEMANTIC_REVIEW_INVALID_RESPONSE"
                assert invalid_code is not None
                async with self._database.session_scope() as session:
                    existing = await self._ai_runs.invalidate_succeeded(
                        session,
                        build_id=build_id,
                        run_key=run_key,
                        error_code=invalid_code,
                        admission_token=admission_token,
                    )

            previous_usage = existing.usage if existing is not None else None
            previous_cost = existing.cost if existing is not None else None
            try:
                generated = await self._ai.structured_generate(
                    model=model,
                    messages=[
                        {"role": "system", "content": SEMANTIC_REVIEW_PROMPT.system},
                        {"role": "user", "content": context},
                    ],
                    response_model=SemanticReviewResult,
                    schema_name="semantic_review_v1",
                )
            except Exception as exc:
                usage = (
                    exc.usage
                    if isinstance(exc, StructuredGenerationError)
                    else unavailable_structured_evidence(field="usage")
                )
                cost = (
                    exc.cost
                    if isinstance(exc, StructuredGenerationError)
                    else unavailable_structured_evidence(field="cost")
                )
                await self._save(
                    build_id=build_id,
                    run_key=run_key,
                    model=model,
                    context_sha256=context_sha256,
                    response=None,
                    response_sha256=None,
                    usage=merge_structured_evidence(previous_usage, usage, field="usage"),
                    cost=merge_structured_evidence(previous_cost, cost, field="cost"),
                    latency_ms=(
                        exc.latency_ms if isinstance(exc, StructuredGenerationError) else None
                    ),
                    status="failed",
                    error_code=(exc.code if isinstance(exc, MCPlicaError) else type(exc).__name__),
                    admission_token=admission_token,
                )
                raise

            result = generated.value
            usage = merge_structured_evidence(
                previous_usage,
                generated.usage or unavailable_structured_evidence(field="usage"),
                field="usage",
            )
            cost = merge_structured_evidence(
                previous_cost,
                generated.cost or unavailable_structured_evidence(field="cost"),
                field="cost",
            )
            unknown = _unknown_operations(result, known_operations)
            if unknown:
                await self._save(
                    build_id=build_id,
                    run_key=run_key,
                    model=generated.model,
                    context_sha256=context_sha256,
                    response=None,
                    response_sha256=None,
                    usage=usage,
                    cost=cost,
                    latency_ms=generated.latency_ms,
                    status="failed",
                    error_code="SEMANTIC_REVIEW_UNKNOWN_OPERATION",
                    admission_token=admission_token,
                )
                raise AIAnalysisError(
                    "Semantic review referenced unknown operations",
                    details={"operation_keys": sorted(unknown)},
                )

            await self._save(
                build_id=build_id,
                run_key=run_key,
                model=generated.model,
                context_sha256=context_sha256,
                response=result.model_dump(mode="json"),
                response_sha256=generated.response_sha256,
                usage=usage,
                cost=cost,
                latency_ms=generated.latency_ms,
                status="succeeded",
                error_code=None,
                admission_token=admission_token,
            )
            findings.extend(result.findings)
        return findings

    async def _save(
        self,
        *,
        build_id: UUID,
        run_key: str,
        model: str,
        context_sha256: str,
        response: dict[str, object] | None,
        response_sha256: str | None,
        usage: dict[str, Any] | None,
        cost: dict[str, Any] | None,
        latency_ms: int | None,
        status: str,
        error_code: str | None,
        admission_token: UUID,
    ) -> None:
        async with self._database.session_scope() as session:
            await self._ai_runs.create(
                session,
                build_id=build_id,
                run_key=run_key,
                stage="semantic_validation",
                operation_key=None,
                model=model,
                prompt_template_id=SEMANTIC_REVIEW_PROMPT.id,
                prompt_template_version=SEMANTIC_REVIEW_PROMPT.version,
                input_context_sha256=context_sha256,
                retrieved_chunk_ids=[],
                response_schema_id=SEMANTIC_REVIEW_PROMPT.response_schema_id,
                response_sha256=response_sha256,
                response_json=response,
                usage=usage,
                cost=cost,
                latency_ms=latency_ms,
                status=status,
                error_code=error_code,
                admission_token=admission_token,
            )


def _batched_contexts(
    canonical: CanonicalApi,
    manifest: MCPManifest,
    max_context_chars: int,
) -> list[str]:
    tools = {tool.operation_key: tool for tool in manifest.tools}
    rows: list[dict[str, object]] = []
    for operation in sorted(canonical.operations, key=lambda item: item.key):
        tool = tools.get(operation.key)
        if tool is None:
            continue
        rows.append(
            {
                "operation_key": operation.key,
                "source": {
                    "method": operation.method.value,
                    "path": operation.path_template,
                    "summary": operation.summary,
                    "description": operation.description,
                },
                "generated": {
                    "tool_name": tool.name,
                    "title": tool.title,
                    "description": tool.description,
                },
            }
        )
    contexts: list[str] = []
    batch: list[dict[str, object]] = []
    for row in rows:
        candidate = _encode(batch + [row])
        if len(candidate) <= max_context_chars:
            batch.append(row)
            continue
        if not batch:
            raise AIAnalysisError(
                "One semantic review item exceeds the configured AI context limit"
            )
        contexts.append(_encode(batch))
        batch = [row]
        if len(_encode(batch)) > max_context_chars:
            raise AIAnalysisError(
                "One semantic review item exceeds the configured AI context limit"
            )
    if batch:
        contexts.append(_encode(batch))
    return contexts


def _encode(rows: list[dict[str, object]]) -> str:
    return json.dumps(
        {"authoritative_source_and_generated_semantics": rows},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _unknown_operations(
    result: SemanticReviewResult,
    known_operations: set[str],
) -> set[str]:
    return {
        item.operation_key
        for item in result.findings
        if item.operation_key is not None and item.operation_key not in known_operations
    }
