"""Reproducible local scale harness for the deterministic Builder pipeline."""

import argparse
import hashlib
import json
import platform
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from mcp_contracts.json_types import JsonObject

from app.compilers.mcp.compiler import compile_manifest
from app.core.canonical_json import canonical_json_bytes
from app.parsers.openapi.parser import parse_openapi
from app.validators.build import FindingSeverity, validate_build

_PROJECT_ID = UUID("00000000-0000-0000-0000-000000000001")
_SOURCE_VERSION_ID = UUID("00000000-0000-0000-0000-000000000002")
_BUILD_ID = UUID("00000000-0000-0000-0000-000000000003")
_CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    parse_seconds: float
    compile_seconds: float
    validation_seconds: float
    total_seconds: float
    manifest_bytes: int


def _openapi_document(operation_count: int) -> JsonObject:
    paths: JsonObject = {}
    for index in range(operation_count):
        paths[f"/resources/{index}"] = {
            "get": {
                "operationId": f"getResource{index}",
                "summary": f"Get resource {index}",
                "responses": {
                    "200": {
                        "description": "Resource response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"id": {"type": "integer"}},
                                    "required": ["id"],
                                }
                            }
                        },
                    }
                },
            }
        }
    return {
        "openapi": "3.1.0",
        "info": {"title": "MCPlica scale fixture", "version": "1.0.0"},
        "servers": [{"url": "https://benchmark.example.com"}],
        "paths": paths,
    }


def run_sample(operation_count: int) -> BenchmarkSample:
    source = _openapi_document(operation_count)
    source_bytes = canonical_json_bytes(source)
    started = time.perf_counter()

    parse_started = time.perf_counter()
    canonical = parse_openapi(
        source,
        project_id=_PROJECT_ID,
        source_version_id=_SOURCE_VERSION_ID,
        content_sha256=hashlib.sha256(source_bytes).hexdigest(),
    )
    parse_seconds = time.perf_counter() - parse_started
    canonical_sha256 = hashlib.sha256(canonical_json_bytes(canonical)).hexdigest()

    compile_started = time.perf_counter()
    manifest = compile_manifest(
        canonical,
        project_id=str(_PROJECT_ID),
        project_name="MCPlica scale fixture",
        project_slug="mcplica-scale-fixture",
        build_id=str(_BUILD_ID),
        created_at=_CREATED_AT,
        canonical_digest=canonical_sha256,
        analysis_model="benchmark/analysis",
        validation_model="benchmark/validation",
        prompt_bundle_version="benchmark-v1",
    )
    compile_seconds = time.perf_counter() - compile_started

    validation_started = time.perf_counter()
    findings = validate_build(
        canonical,
        manifest,
        excluded_operation_keys=frozenset(),
        canonical_sha256=canonical_sha256,
        runtime_version="1.0.0",
    )
    validation_seconds = time.perf_counter() - validation_started
    errors = [finding.code for finding in findings if finding.severity is FindingSeverity.ERROR]
    if errors:
        raise RuntimeError("Scale fixture failed deterministic validation: " + ", ".join(errors))

    manifest_bytes = canonical_json_bytes(manifest)
    return BenchmarkSample(
        parse_seconds=round(parse_seconds, 6),
        compile_seconds=round(compile_seconds, 6),
        validation_seconds=round(validation_seconds, 6),
        total_seconds=round(time.perf_counter() - started, 6),
        manifest_bytes=len(manifest_bytes),
    )


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operations", type=int, default=1_000)
    parser.add_argument("--iterations", type=int, default=3)
    arguments = parser.parse_args()
    if not 1 <= cast(int, arguments.operations) <= 10_000:
        parser.error("--operations must be between 1 and 10000")
    if not 1 <= cast(int, arguments.iterations) <= 20:
        parser.error("--iterations must be between 1 and 20")
    return arguments


def main() -> None:
    arguments = _arguments()
    operation_count = cast(int, arguments.operations)
    samples = [run_sample(operation_count) for _ in range(cast(int, arguments.iterations))]
    totals = [sample.total_seconds for sample in samples]
    print(
        json.dumps(
            {
                "schema_version": "mcplica-builder-benchmark/v1",
                "python": platform.python_version(),
                "platform": platform.platform(),
                "operation_count": operation_count,
                "iterations": len(samples),
                "median_total_seconds": round(statistics.median(totals), 6),
                "samples": [asdict(sample) for sample in samples],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
