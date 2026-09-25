import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import httpx
import pytest
from rq.logutils import setup_loghandlers
from tests.test_log_archive import make_logger, records

from app.core.config import Settings
from app.core.logging import SafeStreamHandler, configure_logging
from app.domain.builds import BuildStatus
from app.jobs import worker_logging
from app.main import create_app
from app.models.audit import AuditEvent
from app.repositories.audit import AuditRepository
from app.services.builds import pipeline as pipeline_module
from app.services.builds.pipeline import BuildPipeline


async def test_audit_append_uses_database_without_file_archive(tmp_path, preserve_logging):
    configure_logging("INFO", directory=str(tmp_path), service="mcplica-api")

    async def refresh(model):
        model.id = uuid4()
        model.created_at = datetime.now(UTC)

    session = SimpleNamespace(add=Mock(), flush=AsyncMock(), refresh=AsyncMock(side_effect=refresh))
    result = await AuditRepository().append(
        session,
        actor_user_id=None,
        event_type="project.created",
        entity_type="project",
        entity_id=uuid4(),
        metadata={"password": "DO_NOT_PRINT"},
    )
    model = session.add.call_args.args[0]
    assert isinstance(model, AuditEvent)
    assert model.__tablename__ == "audit_events"
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(model)
    assert result.event_type == "project.created"
    assert "DO_NOT_PRINT" not in str(model.metadata_json)
    assert not list(tmp_path.rglob("*"))


@pytest.fixture
def preserve_logging():
    names = ("", "uvicorn", "uvicorn.error", "uvicorn.access", "rq.worker", "rq.scheduler")
    snapshots = [
        (
            logging.getLogger(name),
            list(logging.getLogger(name).handlers),
            logging.getLogger(name).level,
            logging.getLogger(name).propagate,
        )
        for name in names
    ]
    yield
    for logger, handlers, level, propagate in snapshots:
        logger.handlers = handlers
        logger.setLevel(level)
        logger.propagate = propagate


async def test_api_requests_archive_safe_context(tmp_path, preserve_logging):
    app = create_app(Settings(_env_file=None, env="test", log_directory=str(tmp_path)))
    transport = httpx.ASGITransport(app=app)
    request_id = str(uuid4())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.get(
            "/api/v1/health?token=DO_NOT_PRINT", headers={"X-Request-ID": request_id}
        )
        second = await client.get("/api/v1/health", headers={"X-Request-ID": "DO_NOT_PRINT"})
    assert first.status_code == second.status_code == 200
    assert first.headers["X-Request-ID"] == request_id
    UUID(second.headers["X-Request-ID"])
    logging.getLogger("mcplica.api").info("platform.after")
    values = records(tmp_path)
    requests = [r for r in values if r["message"] == "request.completed"]
    assert len(requests) == 2
    assert {r["request_id"] for r in requests} == {request_id, second.headers["X-Request-ID"]}
    assert all(r["scope"] == "platform" and r["service"] == "mcplica-api" for r in requests)
    assert "request_id" not in next(r for r in values if r["message"] == "platform.after")
    assert "DO_NOT_PRINT" not in str(values)


@pytest.mark.parametrize("status", [BuildStatus.READY, BuildStatus.FAILED])
async def test_build_lifecycle_events_follow_committed_state(tmp_path, monkeypatch, status):
    logger, _ = make_logger(tmp_path)
    monkeypatch.setattr(pipeline_module, "logger", logger)
    initial = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        requested_by=uuid4(),
        status=BuildStatus.PACKAGING,
        sequence=1,
        manifest_sha256="hash",
        artifact_sha256="hash",
    )
    final = SimpleNamespace(**{**vars(initial), "status": status})
    committed = []

    @asynccontextmanager
    async def session_scope():
        yield object()
        committed.append(True)

    pipeline = object.__new__(BuildPipeline)
    pipeline._database = SimpleNamespace(session_scope=session_scope)
    pipeline._audit = SimpleNamespace(append=AsyncMock())
    pipeline._builds = SimpleNamespace(
        get=AsyncMock(side_effect=[initial, final]),
        fail=AsyncMock(),
        mark_ready=AsyncMock(return_value=final),
    )
    if status == BuildStatus.READY:
        pipeline._get = AsyncMock(return_value=initial)
        pipeline._execution_checkpoint = AsyncMock()
        pipeline._package = AsyncMock()
        result = await pipeline.run(initial.id, uuid4())
        expected = "build.ready"
    else:
        result = await pipeline.fail(
            initial.id,
            admission_token=uuid4(),
            code="BUILD_FAILED",
            summary="password=DO_NOT_PRINT",
        )
        expected = "build.failed"
    assert committed and result is final
    values = records(tmp_path)
    record = next(value for value in values if value["message"] == expected)
    if status == BuildStatus.READY:
        assert {value["message"] for value in values} == {
            "build.started",
            "build.stage_changed",
            "build.ready",
        }
    assert record["message"] == expected
    assert record["project_id"] == str(initial.project_id)
    assert record["build_id"] == str(initial.id)
    assert record["scope"] == "build"
    assert "DO_NOT_PRINT" not in str(record)


async def test_failed_commit_does_not_emit_ready(tmp_path, monkeypatch):
    logger, _ = make_logger(tmp_path)
    monkeypatch.setattr(pipeline_module, "logger", logger)

    @asynccontextmanager
    async def session_scope():
        yield object()
        raise RuntimeError("commit failed")

    build = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        requested_by=uuid4(),
        sequence=1,
        manifest_sha256="hash",
        artifact_sha256="hash",
    )
    pipeline = object.__new__(BuildPipeline)
    pipeline._database = SimpleNamespace(session_scope=session_scope)
    pipeline._audit = SimpleNamespace(append=AsyncMock())
    pipeline._builds = SimpleNamespace(mark_ready=AsyncMock(return_value=build))
    with pytest.raises(RuntimeError, match="commit failed"):
        await pipeline._ready(build.id, uuid4())
    assert not records(tmp_path)


async def test_build_execution_survives_logging_failure_and_cleans_context(tmp_path, monkeypatch):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    logger, handler = make_logger(blocked)
    monkeypatch.setattr(pipeline_module, "logger", logger)
    build = SimpleNamespace(id=uuid4(), project_id=uuid4(), status=BuildStatus.QUEUED)
    pipeline = object.__new__(BuildPipeline)
    pipeline._get = AsyncMock(return_value=build)
    pipeline._run = AsyncMock(return_value=build)
    assert await pipeline.run(build.id, uuid4()) is build
    assert handler.failures == 1
    healthy, _ = make_logger(tmp_path / "healthy")
    healthy.info("after.job")
    assert records(tmp_path / "healthy")[0]["scope"] == "platform"


@pytest.mark.parametrize("service", ["mcplica-builder", "mcplica-deployment"])
def test_worker_entrypoint_and_rq_scheduler_use_safe_logging(
    tmp_path, monkeypatch, preserve_logging, service
):
    monkeypatch.setattr(
        worker_logging,
        "get_settings",
        lambda: Settings(_env_file=None, log_directory=str(tmp_path)),
    )
    monkeypatch.setattr(
        worker_logging.sys, "argv", ["worker_logging", service, "--with-scheduler", "queue"]
    )
    captured = []

    def cli(*, args):
        captured.extend(args)
        for name in ("rq.worker", "rq.scheduler"):
            setup_loghandlers(name=name)
            assert not logging.getLogger(name).handlers
            logging.getLogger(name).info("worker.processing", extra={"password": "DO_NOT_PRINT"})

    monkeypatch.setattr(worker_logging, "main", cli)
    worker_logging.run()
    assert captured == ["worker", "--with-scheduler", "queue"]
    assert len(records(tmp_path)) == 2
    assert all(r["service"] == service for r in records(tmp_path))
    assert "DO_NOT_PRINT" not in str(records(tmp_path))


def test_console_failure_does_not_print_original_record(capsys):
    handler = SafeStreamHandler()
    record = logging.LogRecord("mcplica", logging.INFO, "", 0, "DO_NOT_PRINT", (), None)
    handler.handleError(record)
    assert "DO_NOT_PRINT" not in capsys.readouterr().err


def test_log_level_filters_rq_explicit_logger_level(tmp_path, preserve_logging):
    configure_logging("WARNING", service="mcplica-builder", directory=str(tmp_path))
    setup_loghandlers(name="rq.worker", level="INFO")
    logger = logging.getLogger("rq.worker")
    logger.info("worker.started")
    logger.warning("worker.warning")
    assert [record["message"] for record in records(tmp_path)] == ["worker.warning"]
