import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any
from uuid import UUID

from mcp_contracts import (
    CanonicalApi,
    CanonicalOperation,
    OperationSemanticMetadata,
    SemanticProvenance,
)

from app.clients.database import DatabaseClient
from app.core.async_utils import bounded_map
from app.core.canonical_json import canonical_json_bytes
from app.core.exceptions import AIAnalysisError, MCPlicaError
from app.domain.analysis import (
    EnrichmentSnapshot,
    OperationEnrichment,
    OperationEnrichmentResult,
)
from app.domain.indexing import DocumentIndexGenerationRecord
from app.prompts import OPERATION_ENRICHMENT_PROMPT
from app.providers.ai.base import (
    AIProvider,
    StructuredGenerationError,
    unavailable_structured_evidence,
)
from app.repositories.builds import BuildAIRunRepository
from app.services.analysis.retrieval import RetrievalContext, RetrievalService


class AnalysisService:
    def __init__(
        self,
        database: DatabaseClient,
        ai: AIProvider,
        retrieval: RetrievalService,
        ai_runs: BuildAIRunRepository,
    ) -> None:
        self._database = database
        self._ai = ai
        self._retrieval = retrieval
        self._ai_runs = ai_runs

    async def analyze(
        self,
        *,
        build_id: UUID,
        canonical: CanonicalApi,
        generation: DocumentIndexGenerationRecord,
        model: str,
        include_documentation: bool,
        max_context_chars: int,
        max_concurrency: int,
        retrieval_top_k: int,
        reusable: Mapping[str, OperationEnrichment] | None = None,
        admission_token: UUID,
        cancellation_check: Callable[[], Awaitable[None]] | None = None,
    ) -> EnrichmentSnapshot:
        async def one(operation: CanonicalOperation) -> OperationEnrichment:
            if cancellation_check is not None:
                await cancellation_check()
            return await self._analyze_operation(
                build_id=build_id,
                operation=operation,
                generation=generation,
                model=model,
                include_documentation=include_documentation,
                max_context_chars=max_context_chars,
                retrieval_top_k=retrieval_top_k,
                reusable=(reusable or {}).get(operation.key),
                cancellation_check=cancellation_check,
                admission_token=admission_token,
            )

        operations = sorted(canonical.operations, key=lambda item: item.key)
        completed = await bounded_map(operations, one, limit=max_concurrency)
        return EnrichmentSnapshot(operations={item.operation_key: item for item in completed})

    async def _analyze_operation(
        self,
        *,
        build_id: UUID,
        operation: CanonicalOperation,
        generation: DocumentIndexGenerationRecord,
        model: str,
        include_documentation: bool,
        max_context_chars: int,
        retrieval_top_k: int,
        reusable: OperationEnrichment | None,
        cancellation_check: Callable[[], Awaitable[None]] | None,
        admission_token: UUID,
    ) -> OperationEnrichment:
        run_key = "operation:" + hashlib.sha256(operation.key.encode()).hexdigest()[:32]
        async with self._database.session_scope() as session:
            previous = await self._ai_runs.get_by_run_key(
                session,
                build_id=build_id,
                run_key=run_key,
            )
        if previous is not None and previous.status == "succeeded":
            if previous.response is None:
                raise AIAnalysisError("Successful AI audit row has no structured response")
            result = OperationEnrichmentResult.model_validate(previous.response)
            self._validate_result(operation, result, set(previous.retrieved_chunk_ids))
            if cancellation_check is not None:
                await cancellation_check()
            return _enrichment(
                result,
                model=previous.model,
                context_sha256=previous.input_context_sha256,
                retrieved_chunk_ids=previous.retrieved_chunk_ids,
            )

        if reusable is not None:
            result = OperationEnrichmentResult.model_validate(
                reusable.model_dump(exclude={"provenance"})
            )
            retrieved_chunk_ids = reusable.provenance.retrieved_chunk_ids
            self._validate_result(operation, result, set(retrieved_chunk_ids))
            response = result.model_dump(mode="json")
            await self._save_run(
                build_id=build_id,
                run_key=run_key,
                operation_key=operation.key,
                model=reusable.provenance.model,
                context_sha256=reusable.provenance.context_sha256,
                chunk_ids=retrieved_chunk_ids,
                response=response,
                response_sha256=hashlib.sha256(canonical_json_bytes(response)).hexdigest(),
                usage=None,
                cost=None,
                latency_ms=0,
                status="succeeded",
                error_code=None,
                stage="analysis_reuse",
                admission_token=admission_token,
            )
            if cancellation_check is not None:
                await cancellation_check()
            return reusable

        retrieval = await self._retrieval.retrieve(
            operation,
            generation=generation,
            include_documentation=include_documentation,
            limit=retrieval_top_k,
            max_context_chars=max(1_000, max_context_chars // 2),
            cancellation_check=cancellation_check,
        )
        context = _context(operation, retrieval, max_context_chars=max_context_chars)
        context_sha256 = hashlib.sha256(context.encode()).hexdigest()
        chunk_ids = [chunk.chunk_id for chunk in retrieval.chunks]
        if cancellation_check is not None:
            await cancellation_check()
        try:
            generated = await self._ai.structured_generate(
                model=model,
                messages=[
                    {"role": "system", "content": OPERATION_ENRICHMENT_PROMPT.system},
                    {"role": "user", "content": context},
                ],
                response_model=OperationEnrichmentResult,
                schema_name="operation_enrichment_v1",
            )
            self._validate_result(operation, generated.value, set(chunk_ids))
        except Exception as exc:
            generation_usage = (
                exc.usage
                if isinstance(exc, StructuredGenerationError)
                else unavailable_structured_evidence(field="usage")
            )
            generation_cost = (
                exc.cost
                if isinstance(exc, StructuredGenerationError)
                else unavailable_structured_evidence(field="cost")
            )
            await self._save_run(
                build_id=build_id,
                run_key=run_key,
                operation_key=operation.key,
                model=model,
                context_sha256=context_sha256,
                chunk_ids=chunk_ids,
                response=None,
                response_sha256=None,
                usage=_combined_usage(generation_usage, retrieval),
                cost=generation_cost,
                latency_ms=(exc.latency_ms if isinstance(exc, StructuredGenerationError) else None),
                status="failed",
                error_code=(exc.code if isinstance(exc, MCPlicaError) else type(exc).__name__),
                admission_token=admission_token,
            )
            raise
        await self._save_run(
            build_id=build_id,
            run_key=run_key,
            operation_key=operation.key,
            model=generated.model,
            context_sha256=context_sha256,
            chunk_ids=chunk_ids,
            response=generated.value.model_dump(mode="json"),
            response_sha256=generated.response_sha256,
            usage=_combined_usage(generated.usage, retrieval),
            cost=generated.cost,
            latency_ms=generated.latency_ms,
            status="succeeded",
            error_code=None,
            admission_token=admission_token,
        )
        if cancellation_check is not None:
            await cancellation_check()
        return _enrichment(
            generated.value,
            model=generated.model,
            context_sha256=context_sha256,
            retrieved_chunk_ids=chunk_ids,
        )

    async def _save_run(
        self,
        *,
        build_id: UUID,
        run_key: str,
        operation_key: str,
        model: str,
        context_sha256: str,
        chunk_ids: list[str],
        response: dict[str, object] | None,
        response_sha256: str | None,
        usage: dict[str, Any] | None,
        cost: dict[str, Any] | None,
        latency_ms: int | None,
        status: str,
        error_code: str | None,
        stage: str = "analysis",
        admission_token: UUID,
    ) -> None:
        async with self._database.session_scope() as session:
            await self._ai_runs.create(
                session,
                build_id=build_id,
                run_key=run_key,
                stage=stage,
                operation_key=operation_key,
                model=model,
                prompt_template_id=OPERATION_ENRICHMENT_PROMPT.id,
                prompt_template_version=OPERATION_ENRICHMENT_PROMPT.version,
                input_context_sha256=context_sha256,
                retrieved_chunk_ids=chunk_ids,
                response_schema_id=OPERATION_ENRICHMENT_PROMPT.response_schema_id,
                response_sha256=response_sha256,
                response_json=response,
                usage=usage,
                cost=cost,
                latency_ms=latency_ms,
                status=status,
                error_code=error_code,
                admission_token=admission_token,
            )

    @staticmethod
    def _validate_result(
        operation: CanonicalOperation,
        result: OperationEnrichmentResult,
        retrieved_chunk_ids: set[str],
    ) -> None:
        if result.operation_key != operation.key:
            raise AIAnalysisError("AI enrichment changed the operation identity")
        invented_chunks = set(result.documentation_chunk_ids) - retrieved_chunk_ids
        if invented_chunks:
            raise AIAnalysisError(
                "AI enrichment cited documentation outside the bounded retrieval context",
                details={"chunk_ids": sorted(invented_chunks)},
            )

    @staticmethod
    def apply(canonical: CanonicalApi, enrichment: EnrichmentSnapshot) -> CanonicalApi:
        known = {operation.key for operation in canonical.operations}
        if set(enrichment.operations) != known:
            raise AIAnalysisError("Semantic enrichment does not cover the canonical operations")
        operations: list[CanonicalOperation] = []
        for operation in canonical.operations:
            value = enrichment.operations[operation.key]
            operations.append(
                operation.model_copy(
                    update={
                        "semantic": OperationSemanticMetadata(
                            title=value.title,
                            description=value.description,
                            category=value.category,
                            keywords=value.keywords,
                            documentation_chunk_ids=value.documentation_chunk_ids,
                            relationship_hints=value.relationship_hints,
                            confidence=value.confidence,
                            provenance=value.provenance,
                        )
                    }
                )
            )
        return canonical.model_copy(update={"operations": operations})


def _enrichment(
    result: OperationEnrichmentResult,
    *,
    model: str,
    context_sha256: str,
    retrieved_chunk_ids: list[str],
) -> OperationEnrichment:
    return OperationEnrichment(
        **result.model_dump(),
        provenance=SemanticProvenance(
            provider="openrouter",
            model=model,
            prompt_template_id=OPERATION_ENRICHMENT_PROMPT.id,
            prompt_template_version=OPERATION_ENRICHMENT_PROMPT.version,
            context_sha256=context_sha256,
            retrieved_chunk_ids=retrieved_chunk_ids,
        ),
    )


def _context(
    operation: CanonicalOperation,
    retrieval: RetrievalContext,
    *,
    max_context_chars: int,
) -> str:
    payload: dict[str, object] = {
        "authoritative_source_facts": _source_facts(operation),
        "untrusted_documentation_excerpts": [
            {
                "chunk_id": chunk.chunk_id,
                "title": chunk.title,
                "section_path": chunk.section_path,
                "text": chunk.text,
            }
            for chunk in retrieval.chunks
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    while len(encoded) > max_context_chars and payload["untrusted_documentation_excerpts"]:
        excerpts = payload["untrusted_documentation_excerpts"]
        assert isinstance(excerpts, list)
        excerpts.pop()
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(encoded) > max_context_chars:
        raise AIAnalysisError("Authoritative operation context exceeds the configured AI limit")
    return encoded


def _source_facts(operation: CanonicalOperation) -> dict[str, object]:
    return {
        "operation_key": operation.key,
        "operation_id": operation.source_operation_id,
        "method": operation.method.value,
        "path": operation.path_template,
        "summary": (operation.summary or "")[:2_000],
        "description": (operation.description or "")[:8_000],
        "tags": operation.tags[:50],
        "parameters": [
            {
                "name": parameter.name,
                "location": parameter.location.value,
                "required": parameter.required,
                "schema_sha256": hashlib.sha256(
                    canonical_json_bytes(parameter.schema_)
                ).hexdigest(),
            }
            for parameter in operation.parameters
        ],
        "request_media_types": (
            [item.media_type for item in operation.request_body.content]
            if operation.request_body
            else []
        ),
        "response_statuses": [response.status_code for response in operation.responses],
        "security_schemes": sorted(
            {name for requirement in operation.security for name in requirement.scheme_scopes}
        ),
    }


def _combined_usage(
    generation_usage: dict[str, Any] | None,
    retrieval: RetrievalContext,
) -> dict[str, Any] | None:
    if generation_usage is None and retrieval.embedding_usage is None:
        return None
    return {
        "structured_generation": generation_usage,
        "retrieval_embedding": retrieval.embedding_usage,
    }
