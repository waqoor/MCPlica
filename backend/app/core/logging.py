import json
import logging
import math
import re
from datetime import UTC, datetime
from typing import ClassVar, cast
from urllib.parse import urlsplit

_EVENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _safe_event_name(record: logging.LogRecord) -> str:
    value = record.msg
    if isinstance(value, str) and _EVENT_NAME.fullmatch(value):
        return value
    return "log.message_omitted"


def _safe_pg_diag(current: BaseException) -> dict[str, object]:
    orig = getattr(current, "orig", None)
    diag = getattr(orig, "diag", None)
    constraint_name = getattr(diag, "constraint_name", None)
    if not isinstance(constraint_name, str) or not _EVENT_NAME.fullmatch(constraint_name):
        return {}
    # PostgreSQL details can contain entire private rows, including credentials.
    return {"pg_constraint": constraint_name}


def _safe_exception(
    exc_info: tuple[type[BaseException] | None, BaseException | None, object],
) -> dict[str, object]:
    current: BaseException | None = exc_info[1]
    chain: list[str] = []
    seen: set[int] = set()
    diag: dict[str, object] = {}
    while current is not None and id(current) not in seen and len(chain) < 8:
        seen.add(id(current))
        chain.append(type(current).__name__)
        if not diag:
            diag = _safe_pg_diag(current)
        current = current.__cause__ or current.__context__
    if not chain:
        return {"type": "Exception"}
    result: dict[str, object] = {"type": chain[0], "chain": chain, **diag}
    return result


_CONTEXT_FIELDS: tuple[str, ...] = (
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
    "run_key",
    "op",
    "existing_status",
    "new_status",
    "response_json_is_none",
    "response_sha256_is_none",
)


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
    return value


class JsonLogFormatter(logging.Formatter):
    """Small stdlib formatter so every process emits the same safe JSON envelope."""

    context_fields: ClassVar[tuple[str, ...]] = _CONTEXT_FIELDS

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "service": getattr(record, "service", "mcplica"),
            "component": getattr(record, "component", record.name),
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
        rendered = f"{timestamp} {record.levelname} {record.name} {_safe_event_name(record)}"
        for field in _CONTEXT_FIELDS:
            value = getattr(record, field, None)
            safe_value = _safe_context_value(field, value)
            if safe_value is not None:
                rendered += f" {field}={safe_value}"
        if record.exc_info:
            exception = _safe_exception(record.exc_info)
            rendered += f" exception_type={exception['type']}"
            chain = cast(list[str], exception.get("chain", []))
            if len(chain) > 1:
                rendered += f" exception_chain={'<-'.join(chain)}"
            if "pg_constraint" in exception:
                rendered += f" pg_constraint={exception['pg_constraint']}"
        return rendered


def configure_logging(level: str, *, json_logs: bool = False) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter() if json_logs else SafeTextLogFormatter())
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[handler],
        force=True,
    )
