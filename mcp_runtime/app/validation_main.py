import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast

from mcp_contracts import MCPManifest
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from app.core.logging import configure_runtime_logging
from app.validation_harness import inspect_runtime_candidate


class RuntimeValidatorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_", extra="ignore")

    runtime_version: str = Field(default="1.0.0", min_length=1, max_length=64)
    max_manifest_bytes: int = Field(default=10_000_000, ge=1_024, le=50_000_000)
    validator_max_concurrency: int = Field(default=2, ge=1, le=32)
    validator_timeout_seconds: float = Field(default=60.0, gt=0.0, le=600.0)
    log_level: str = "INFO"


settings = RuntimeValidatorSettings()
configure_runtime_logging(settings.log_level)
logger = logging.getLogger("mcplica.runtime-validator")


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncGenerator[None]:
    app.state.validation_slots = asyncio.Semaphore(settings.validator_max_concurrency)
    yield


async def health(_: Request) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "service": "mcplica-runtime-validator",
            "runtime_version": settings.runtime_version,
        }
    )


async def validate_candidate(request: Request) -> Response:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        return _rejection(415, "content_type_invalid", "Content-Type must be application/json")
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            declared_bytes = int(declared)
        except ValueError:
            return _rejection(400, "content_length_invalid", "Content-Length is invalid")
        if declared_bytes < 0 or declared_bytes > settings.max_manifest_bytes:
            return _rejection(413, "manifest_too_large", "Manifest exceeds the byte limit")
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > settings.max_manifest_bytes:
            return _rejection(413, "manifest_too_large", "Manifest exceeds the byte limit")
    try:
        manifest = MCPManifest.model_validate_json(bytes(payload))
    except ValidationError:
        return _rejection(422, "manifest_invalid", "Manifest does not match the contract")

    semaphore = cast(asyncio.Semaphore, request.app.state.validation_slots)
    try:
        async with semaphore, asyncio.timeout(settings.validator_timeout_seconds):
            report = await inspect_runtime_candidate(
                manifest,
                runtime_version=settings.runtime_version,
            )
    except TimeoutError:
        return _rejection(422, "runtime_validation_timeout", "Runtime validation timed out")
    except (TypeError, ValueError) as exc:
        logger.info(
            "runtime_candidate_rejected",
            extra={"error_type": type(exc).__name__},
        )
        return _rejection(422, "runtime_rejected_manifest", str(exc)[:500])
    except Exception as exc:
        logger.exception(
            "runtime_candidate_validation_failed",
            extra={"error_type": type(exc).__name__},
        )
        return _rejection(
            422,
            "runtime_candidate_execution_failed",
            "Pinned runtime execution did not complete successfully",
        )
    return JSONResponse(report)


def _rejection(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message}},
        status_code=status,
    )


app = Starlette(
    routes=[
        Route("/healthz", health, methods=["GET"]),
        Route("/validate", validate_candidate, methods=["POST"]),
    ],
    lifespan=lifespan,
)
