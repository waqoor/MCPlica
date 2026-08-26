import math
import os
from collections.abc import Mapping

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)

HTTP_REQUESTS = Counter(
    "mcplica_http_requests_total",
    "Control-plane HTTP requests.",
    ("method", "route", "status_class"),
)
HTTP_REQUEST_DURATION = Histogram(
    "mcplica_http_request_duration_seconds",
    "Control-plane HTTP request duration.",
    ("method", "route"),
)
BUILD_JOBS = Counter(
    "mcplica_build_jobs_total",
    "Builder job attempts by outcome.",
    ("outcome",),
)
BUILD_JOB_DURATION = Histogram(
    "mcplica_build_job_duration_seconds",
    "Builder job-attempt duration.",
    ("outcome",),
)
BUILD_STAGE_DURATION = Histogram(
    "mcplica_build_stage_duration_seconds",
    "Builder stage duration.",
    ("stage", "outcome"),
)
GENERATED_OPERATIONS = Histogram(
    "mcplica_build_generated_operations",
    "Number of operations emitted by a compiled Build.",
    buckets=(0, 1, 5, 10, 25, 50, 100, 250, 500, 1_000, 5_000, 10_000),
)
OPENROUTER_REQUESTS = Counter(
    "mcplica_openrouter_requests_total",
    "Logical OpenRouter requests by operation and outcome.",
    ("operation", "outcome"),
)
OPENROUTER_REQUEST_DURATION = Histogram(
    "mcplica_openrouter_request_duration_seconds",
    "Logical OpenRouter request duration.",
    ("operation", "outcome"),
)
OPENROUTER_RATE_LIMITS = Counter(
    "mcplica_openrouter_rate_limits_total",
    "OpenRouter HTTP 429 responses, including recovered retries.",
    ("operation",),
)
OPENROUTER_USAGE = Counter(
    "mcplica_openrouter_usage_total",
    "Provider-reported OpenRouter token usage.",
    ("token_type",),
)
OPENROUTER_COST = Counter(
    "mcplica_openrouter_cost_total",
    "Provider-reported OpenRouter cost in provider billing units.",
)
MILVUS_OPERATIONS = Counter(
    "mcplica_milvus_operations_total",
    "Milvus client operations by outcome.",
    ("operation", "outcome"),
)
MILVUS_OPERATION_DURATION = Histogram(
    "mcplica_milvus_operation_duration_seconds",
    "Milvus client operation duration.",
    ("operation", "outcome"),
)

METRICS_CONTENT_TYPE = CONTENT_TYPE_LATEST


def observe_http_request(method: str, route: str, status_code: int, duration: float) -> None:
    normalized_status = f"{max(0, status_code) // 100}xx"
    HTTP_REQUESTS.labels(method=method, route=route, status_class=normalized_status).inc()
    HTTP_REQUEST_DURATION.labels(method=method, route=route).observe(max(0.0, duration))


def observe_build_job(outcome: str, duration: float) -> None:
    BUILD_JOBS.labels(outcome=outcome).inc()
    BUILD_JOB_DURATION.labels(outcome=outcome).observe(max(0.0, duration))


def observe_build_stage(stage: str, outcome: str, duration: float) -> None:
    BUILD_STAGE_DURATION.labels(stage=stage, outcome=outcome).observe(max(0.0, duration))


def observe_generated_operations(count: int) -> None:
    GENERATED_OPERATIONS.observe(max(0, count))


def observe_openrouter_request(operation: str, outcome: str, duration: float) -> None:
    OPENROUTER_REQUESTS.labels(operation=operation, outcome=outcome).inc()
    OPENROUTER_REQUEST_DURATION.labels(operation=operation, outcome=outcome).observe(
        max(0.0, duration)
    )


def observe_openrouter_rate_limit(operation: str) -> None:
    OPENROUTER_RATE_LIMITS.labels(operation=operation).inc()


def _nonnegative_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None


def observe_openrouter_usage(usage: Mapping[str, object] | None) -> None:
    if usage is None:
        return
    for provider_key, metric_label in (
        ("prompt_tokens", "prompt"),
        ("completion_tokens", "completion"),
        ("total_tokens", "total"),
    ):
        value = _nonnegative_number(usage.get(provider_key))
        if value is not None:
            OPENROUTER_USAGE.labels(token_type=metric_label).inc(value)
    cost = _nonnegative_number(usage.get("cost"))
    if cost is not None:
        OPENROUTER_COST.inc(cost)


def observe_milvus_operation(operation: str, outcome: str, duration: float) -> None:
    MILVUS_OPERATIONS.labels(operation=operation, outcome=outcome).inc()
    MILVUS_OPERATION_DURATION.labels(operation=operation, outcome=outcome).observe(
        max(0.0, duration)
    )


def render_metrics() -> bytes:
    """Render the current process, or all configured Prometheus worker shards."""
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry)
    return generate_latest(REGISTRY)
