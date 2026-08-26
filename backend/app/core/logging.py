import json
import logging
from datetime import UTC, datetime
from typing import ClassVar


class JsonLogFormatter(logging.Formatter):
    """Small stdlib formatter so every process emits the same safe JSON envelope."""

    context_fields: ClassVar[tuple[str, ...]] = (
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
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "service": getattr(record, "service", "mcplica"),
            "component": getattr(record, "component", record.name),
            "message": record.getMessage(),
        }
        for field in self.context_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str, *, json_logs: bool = False) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonLogFormatter()
        if json_logs
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[handler],
        force=True,
    )
