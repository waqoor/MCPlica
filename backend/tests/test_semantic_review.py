import hashlib
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest

from app.compilers.mcp.compiler import compile_manifest
from app.core.exceptions import AIAnalysisError
from app.domain.analysis import SemanticReviewFinding, SemanticReviewResult
from app.parsers.openapi.parser import parse_openapi
from app.providers.ai.base import (
    StructuredAttempt,
    StructuredGeneration,
    structured_cost_evidence,
    structured_usage_evidence,
)
from app.services.analysis.review import SemanticReviewService


def _canonical_and_manifest():
    canonical = parse_openapi(
        {
            "openapi": "3.1.0",
            "info": {"title": "Review", "version": "1"},
            "servers": [{"url": "https://api.example.test"}],
            "paths": {
                "/items": {
                    "get": {
                        "operationId": "listItems",
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
        },
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(b"review").hexdigest(),
    )
    manifest = compile_manifest(
        canonical,
        project_id=str(UUID(int=1)),
        project_name="Review",
        project_slug="review",
        build_id=str(UUID(int=3)),
        created_at=datetime(2026, 9, 2, tzinfo=UTC),
        security_selections={},
    )
    return canonical, manifest


class _Database:
    @asynccontextmanager
    async def session_scope(self):
        yield object()


class _Runs:
    def __init__(self, record: SimpleNamespace | None = None) -> None:
        self.record = record
        self.invalidations = 0

    async def get_by_run_key(self, _session: object, **_kwargs: object):
        return self.record

    async def invalidate_succeeded(self, _session: object, **kwargs: object):
        assert self.record is not None
        self.invalidations += 1
        self.record.status = "failed"
        self.record.response = None
        self.record.error_code = kwargs["error_code"]
        return self.record

    async def create(self, _session: object, **kwargs: object):
        self.record = SimpleNamespace(
            status=kwargs["status"],
            response=kwargs["response_json"],
            usage=kwargs["usage"],
            cost=kwargs["cost"],
            error_code=kwargs["error_code"],
        )
        return self.record


class _AI:
    def __init__(self, results: list[SemanticReviewResult]) -> None:
        self.results = results
        self.calls = 0

    async def structured_generate(self, **_kwargs: object):
        result = self.results[self.calls]
        self.calls += 1
        usage = {
            "total_tokens": 5 if self.calls == 1 else 10,
            "cost": 0.002 if self.calls == 1 else 0.003,
        }
        attempt = StructuredAttempt(
            ordinal=1,
            outcome="accepted",
            model="test/model",
            usage=usage,
            cost={"cost": usage["cost"]},
            latency_ms=1,
        )
        return StructuredGeneration(
            value=result,
            model="test/model",
            response_sha256=hashlib.sha256(str(self.calls).encode()).hexdigest(),
            usage=structured_usage_evidence((attempt,)),
            cost=structured_cost_evidence((attempt,)),
            latency_ms=1,
            attempts=(attempt,),
        )


async def test_invalid_semantic_response_is_failed_then_retry_can_succeed() -> None:
    canonical, manifest = _canonical_and_manifest()
    known_key = canonical.operations[0].key
    invalid = SemanticReviewResult(
        findings=[
            SemanticReviewFinding(
                code="UNKNOWN_OPERATION",
                severity="warning",
                operation_key="invented_operation",
                message="invalid reference",
            )
        ]
    )
    valid = SemanticReviewResult(
        findings=[
            SemanticReviewFinding(
                code="KNOWN_OPERATION",
                severity="info",
                operation_key=known_key,
                message="valid reference",
            )
        ]
    )
    ai = _AI([invalid, valid])
    runs = _Runs()
    service = SemanticReviewService(
        cast(Any, _Database()),
        cast(Any, ai),
        cast(Any, runs),
    )
    arguments = {
        "build_id": UUID(int=3),
        "canonical": canonical,
        "manifest": manifest,
        "model": "test/model",
        "max_context_chars": 20_000,
        "admission_token": UUID(int=4),
    }

    with pytest.raises(AIAnalysisError, match="unknown operations"):
        await service.review(**arguments)
    assert runs.record is not None
    assert runs.record.status == "failed"
    assert runs.record.response is None
    assert runs.record.usage["total_tokens"] == 5

    findings = await service.review(**arguments)
    assert [finding.operation_key for finding in findings] == [known_key]
    assert runs.record.status == "succeeded"
    assert runs.record.usage["total_tokens"] == 15
    assert runs.record.cost["cost"] == pytest.approx(0.005)
    assert len(runs.record.usage["attempts"]) == 2

    assert await service.review(**arguments) == findings
    assert ai.calls == 2


async def test_historical_invalid_success_is_demoted_before_regeneration() -> None:
    canonical, manifest = _canonical_and_manifest()
    invalid_response = {
        "findings": [
            {
                "code": "UNKNOWN_OPERATION",
                "severity": "warning",
                "operation_key": "invented_operation",
                "message": "invalid reference",
            }
        ]
    }
    prior_attempt = StructuredAttempt(
        ordinal=1,
        outcome="accepted",
        model="test/model",
        usage={"total_tokens": 5, "cost": 0.002},
        cost={"cost": 0.002},
        latency_ms=1,
    )
    runs = _Runs(
        SimpleNamespace(
            status="succeeded",
            response=invalid_response,
            usage=structured_usage_evidence((prior_attempt,)),
            cost=structured_cost_evidence((prior_attempt,)),
            error_code=None,
        )
    )
    ai = _AI([SemanticReviewResult(findings=[])])
    service = SemanticReviewService(
        cast(Any, _Database()),
        cast(Any, ai),
        cast(Any, runs),
    )

    assert (
        await service.review(
            build_id=UUID(int=3),
            canonical=canonical,
            manifest=manifest,
            model="test/model",
            max_context_chars=20_000,
            admission_token=UUID(int=4),
        )
        == []
    )
    assert runs.invalidations == 1
    assert runs.record.status == "succeeded"
    assert runs.record.usage["total_tokens"] == 10
