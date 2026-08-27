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
from app.providers.ai.base import AIProvider
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
                if existing.response is None:
                    raise AIAnalysisError("Successful semantic review row has no response")
                result = SemanticReviewResult.model_validate(existing.response)
            else:
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
                    await self._save(
                        build_id=build_id,
                        run_key=run_key,
                        model=model,
                        context_sha256=context_sha256,
                        response=None,
                        response_sha256=None,
                        usage=None,
                        cost=None,
                        latency_ms=None,
                        status="failed",
                        error_code=(
                            exc.code if isinstance(exc, MCPlicaError) else type(exc).__name__
                        ),
                    )
                    raise
                result = generated.value
                await self._save(
                    build_id=build_id,
                    run_key=run_key,
                    model=generated.model,
                    context_sha256=context_sha256,
                    response=result.model_dump(mode="json"),
                    response_sha256=generated.response_sha256,
                    usage=generated.usage,
                    cost=generated.cost,
                    latency_ms=generated.latency_ms,
                    status="succeeded",
                    error_code=None,
                )
            unknown = {
                item.operation_key
                for item in result.findings
                if item.operation_key is not None and item.operation_key not in known_operations
            }
            if unknown:
                raise AIAnalysisError(
                    "Semantic review referenced unknown operations",
                    details={"operation_keys": sorted(unknown)},
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
