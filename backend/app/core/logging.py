import json
import logging
import math
import re
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlsplit
from uuid import UUID

from app.core.log_archive import ArchiveHandler, report_failure

_EVENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_CONTEXT: ContextVar[dict[str, object] | None] = ContextVar("log_context", default=None)


@contextmanager
def log_context(
    *,
    project_id: UUID | None = None,
    build_id: UUID | None = None,
    request_id: str | None = None,
    correlation_id: str | None = None,
    attempt_number: int | None = None,
) -> Generator[None]:
    """A build archive requires both IDs obtained from authoritative build state."""
    values: dict[str, object] = {}
    if isinstance(project_id, UUID) and isinstance(build_id, UUID):
        values.update(scope="build", project_id=str(project_id), build_id=str(build_id))
        values["_archive_build"] = (str(project_id), str(build_id))
    for key, value in (
        ("request_id", request_id),
        ("correlation_id", correlation_id),
        ("attempt_number", attempt_number),
    ):
        if value is not None:
            values[key] = value
    token = _CONTEXT.set({**(_CONTEXT.get() or {}), **values})
    try:
        yield
    finally:
        _CONTEXT.reset(token)


class ContextFilter(logging.Filter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service
        record.scope = "platform"
        record._archive_build = None
        for key, value in (_CONTEXT.get() or {}).items():
            setattr(record, key, value)
        return True


def _safe_event_name(record: logging.LogRecord) -> str:
    value = record.msg
    if isinstance(value, str) and _EVENT_NAME.fullmatch(value):
        return value
    return "log.message_omitted"


def _safe_exception(
    exc_info: tuple[type[BaseException] | None, BaseException | None, object],
) -> dict[str, object]:
    current: BaseException | None = exc_info[1]
    chain: list[str] = []
    seen: set[int] = set()
    while current is not None and id(current) not in seen and len(chain) < 8:
        seen.add(id(current))
        chain.append(type(current).__name__)
        current = current.__cause__ or current.__context__
    return {"type": chain[0], "chain": chain} if chain else {"type": "Exception"}


def _safe_context_value(field: str, value: object) -> str | int | float | bool | None:
    if isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if not isinstance(value, str) or len(value) > 512:
        return None
    if any(character in value for character in "\r\n\x00"):
        return None
    if field == "route":
        parsed = urlsplit(value)
        return parsed.path or "/"
    if not _EVENT_NAME.fullmatch(value):
        return None
    return value


class JsonLogFormatter(logging.Formatter):
    """Small stdlib formatter so every process emits the same safe JSON envelope."""

    context_fields: ClassVar[tuple[str, ...]] = (
        "scope",
        "correlation_id",
        "stage",
        "outcome",
        "service",
        "component",
        "request_id",
        "job_id",
        "actor_id",
        "project_id",
        "build_id",
        "deployment_id",
        "error_code",
        "method",
        "route",
        "status_code",
        "duration_ms",
        "attempt_number",
        "admission_attempt",
        "cleanup_job_id",
        "cleanup_target_id",
        "runtime_command_id",
        "retryable",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "service": "mcplica",
            "component": _safe_context_value("component", record.name) or "application",
            "message": _safe_event_name(record),
        }
        for field in self.context_fields:
            value = getattr(record, field, None)
            safe_value = _safe_context_value(field, value)
            if safe_value is not None:
                payload[field] = safe_value
        if record.exc_info:
            payload["exception"] = _safe_exception(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class SafeTextLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, UTC).isoformat()
        component = _safe_context_value("component", record.name) or "application"
        rendered = f"{timestamp} {record.levelname} {component} {_safe_event_name(record)}"
        if record.exc_info:
            exception = _safe_exception(record.exc_info)
            rendered += f" exception_type={exception['type']}"
        return rendered


class SafeStreamHandler(logging.StreamHandler):  # pyright: ignore[reportMissingTypeArgument]
    # StreamHandler is generic only in type stubs, not at runtime.
    def handleError(self, record: logging.LogRecord) -> None:
        # Stdlib's debug fallback prints the original message and args on failure.
        report_failure("log.console_write_failed")


def configure_logging(
    level: str,
    *,
    json_logs: bool = False,
    service: str = "mcplica",
    directory: str | None = None,
    max_bytes: int = 10485760,
) -> None:
    threshold = getattr(logging, level.upper(), logging.INFO)
    handler = SafeStreamHandler()
    handler.setLevel(threshold)
    handler.setFormatter(JsonLogFormatter() if json_logs else SafeTextLogFormatter())
    handler.addFilter(ContextFilter(service))
    handlers: list[logging.Handler] = [handler]
    if directory is not None:
        archive = ArchiveHandler(Path(directory), max_bytes)
        archive.setLevel(threshold)
        archive.setFormatter(JsonLogFormatter())
        archive.addFilter(ContextFilter(service))
        handlers.append(archive)
    logging.basicConfig(
        level=threshold,
        handlers=handlers,
        force=True,
    )
    # Uvicorn/RQ may already have console handlers; route through safe formatting.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "rq.worker", "rq.scheduler"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
