import json
import logging
import sys
from datetime import UTC, datetime

_SAFE_CONTEXT_FIELDS = {
    "build_id",
    "deployment_id",
    "error_code",
    "project_id",
    "status",
    "tool_name",
}


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for field in _SAFE_CONTEXT_FIELDS:
            value = getattr(record, field, None)
            if isinstance(value, str | int | float | bool):
                payload[field] = value
        if record.exc_info is not None:
            exception_type = record.exc_info[0]
            if exception_type is not None:
                payload["exception_type"] = exception_type.__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_runtime_logging(level: str) -> None:
    logger = logging.getLogger("mcplica.runtime")
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False
