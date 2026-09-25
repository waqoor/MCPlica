import asyncio
import json
import logging
import os
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.core import log_archive
from app.core.config import Settings
from app.core.log_archive import ArchiveHandler, cleanup_logs
from app.core.logging import ContextFilter, JsonLogFormatter, log_context


def make_logger(root: Path, limit: int = 1024):
    handler = ArchiveHandler(root, limit)
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(ContextFilter("mcplica-builder"))
    logger = logging.Logger("mcplica.test", level=logging.INFO)
    logger.addHandler(handler)
    return logger, handler


def records(root: Path):
    return [
        json.loads(line) for path in root.rglob("*.log") for line in path.read_text().splitlines()
    ]


def test_explicit_routing_and_context_cleanup(tmp_path):
    logger, _ = make_logger(tmp_path)
    project, build = uuid4(), uuid4()
    logger.info(
        "platform.event",
        extra={
            "scope": "build",
            "project_id": str(project),
            "build_id": str(build),
            "_archive_build": (str(project), str(build)),
        },
    )
    with pytest.raises(RuntimeError), log_context(project_id=project, build_id=build):
        logger.info("build.started")
        raise RuntimeError("not logged")
    logger.info("platform.after")
    assert len(list((tmp_path / "platform").rglob("*.log"))) == 1
    assert len(list((tmp_path / "projects" / str(project) / str(build)).rglob("*.log"))) == 1
    after = next(r for r in records(tmp_path) if r["message"] == "platform.after")
    assert after["scope"] == "platform" and "build_id" not in after


def test_project_build_isolation(tmp_path):
    logger, _ = make_logger(tmp_path)
    project = uuid4()
    destinations = [(project, uuid4()), (project, uuid4()), (uuid4(), uuid4())]
    for project_id, build_id in destinations:
        with log_context(project_id=project_id, build_id=build_id):
            logger.info("build.started")
    assert len(list(tmp_path.rglob("*.log"))) == 3


def test_emission_date_not_record_timestamp(tmp_path, monkeypatch):
    logger, _ = make_logger(tmp_path)
    for day in (date(2026, 9, 14), date(2026, 9, 15)):
        monkeypatch.setattr(log_archive, "utc_today", lambda day=day: day)
        record = logger.makeRecord(logger.name, logging.INFO, "", 0, "event", (), None)
        record.created = 0
        logger.handle(record)
    assert {p.parent.name for p in tmp_path.rglob("*.log")} == {"2026-09-14", "2026-09-15"}


def test_utf8_size_and_oversized_record(tmp_path):
    logger, _ = make_logger(tmp_path)
    for _ in range(12):
        logger.info("event", extra={"route": "/" + "文" * 150})
    logger.info("event", extra={"route": "/" + "文" * 400})
    files = list(tmp_path.rglob("*.log"))
    assert len(files) > 1
    assert all(path.suffix == ".log" for path in tmp_path.rglob("*") if path.is_file())
    assert all(p.stat().st_size <= 1024 for p in files)
    values = records(tmp_path)
    assert len(values) == 13
    assert sum(r["message"] == "log.record_omitted" for r in values) == 1
    assert sum(r.get("route") == "/" + "文" * 150 for r in values) == 12


@pytest.mark.parametrize("days", [1, 7, 30])
def test_retention_calendar_boundary_and_unrelated_files(tmp_path, days):
    today = date(2026, 9, 15)
    for age in (0, days - 1, days, days + 1):
        path = tmp_path / "platform" / "mcplica-api" / (today - timedelta(days=age)).isoformat()
        path.mkdir(parents=True, exist_ok=True)
        (path / ("1-" + "a" * 32 + ".0.log")).write_text("{}\n")
        (path / "unrelated.txt").write_text("keep")
    assert cleanup_logs(tmp_path, days, today=today) == 2
    assert len(list(tmp_path.rglob("unrelated.txt"))) == (3 if days == 1 else 4)
    assert all(
        (today - date.fromisoformat(p.parent.name)).days < days for p in tmp_path.rglob("*.log")
    )


def test_default_retention_and_configuration(tmp_path):
    settings = Settings(_env_file=None)
    assert settings.log_retention_days == 30
    assert settings.log_max_file_bytes == 10 * 1024 * 1024
    assert Settings(_env_file=None, log_max_file_bytes=2048).log_max_file_bytes == 2048
    assert settings.log_directory == "/var/log/mcplica"
    assert Settings(_env_file=None, log_retention_days=7).log_retention_days == 7
    for values in (
        {"log_retention_days": 0},
        {"log_max_file_bytes": 100},
        {"log_directory": "/"},
        {"log_directory": "/tmp/../data"},
    ):
        with pytest.raises(ValueError):
            Settings(_env_file=None, **values)
    logger, _ = make_logger(tmp_path)
    with log_context(project_id=uuid4(), build_id=uuid4()):
        logger.info("build.ready")
    assert cleanup_logs(tmp_path, today=log_archive.utc_today() + timedelta(days=30)) == 1
    assert list(tmp_path.iterdir()) == []


def test_symlinks_hardlinks_and_traversal_are_rejected(tmp_path):
    root, outside = tmp_path / "logs", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    sentinel = outside / ("1-" + "a" * 32 + ".0.log")
    sentinel.write_text("keep")
    (root / "platform").symlink_to(outside, target_is_directory=True)
    logger, handler = make_logger(root)
    logger.info("event")
    assert handler.failures == 1
    assert cleanup_logs(root, today=date(2099, 1, 1)) == 0
    (root / "platform").unlink()
    day = root / "platform" / "mcplica-api" / "2000-01-01"
    day.mkdir(parents=True)
    (day / sentinel.name).symlink_to(sentinel)
    os.link(sentinel, day / ("2-" + "a" * 32 + ".0.log"))
    assert cleanup_logs(root) == 0
    assert cleanup_logs(root / ".." / "outside") == 0
    assert sentinel.read_text() == "keep"


def test_write_and_cleanup_failure_do_not_escape(tmp_path, monkeypatch, capsys):
    @contextmanager
    def broken(*args, **kwargs):
        raise OSError("password=DO_NOT_PRINT")
        yield

    monkeypatch.setattr(log_archive, "directory", broken)
    logger, handler = make_logger(tmp_path)
    logger.exception("event")
    logger.info("event")
    assert handler.failures == 2
    assert cleanup_logs(tmp_path) == 0
    output = capsys.readouterr().err
    assert "DO_NOT_PRINT" not in output
    assert output.count("log.archive_write_failed") == 1
    assert "log.retention_failed" in output


def test_sensitive_payload_omission(tmp_path):
    logger, _ = make_logger(tmp_path)
    try:
        raise ValueError("password=DO_NOT_PRINT")
    except ValueError:
        logger.exception(
            "Bearer DO_NOT_PRINT",
            extra={
                "password": "DO_NOT_PRINT",
                "response": "DO_NOT_PRINT",
                "chain_of_thought": "DO_NOT_PRINT",
                "component": "Bearer DO_NOT_PRINT",
                "route": "/api/v1/builds?token=DO_NOT_PRINT",
            },
        )
    text = "".join(p.read_text() for p in tmp_path.rglob("*.log"))
    assert "DO_NOT_PRINT" not in text
    assert records(tmp_path)[0]["exception"]["type"] == "ValueError"


async def test_context_isolated_between_async_requests(tmp_path):
    logger, _ = make_logger(tmp_path)

    async def request(value):
        with log_context(request_id=value):
            await asyncio.sleep(0)
            logger.info("request.completed")

    await asyncio.gather(request("request-1"), request("request-2"))
    logger.info("after")
    values = records(tmp_path)
    assert {r["request_id"] for r in values if r["message"] == "request.completed"} == {
        "request-1",
        "request-2",
    }
    assert "request_id" not in values[-1]


def test_real_fork_and_restart_writer_uniqueness(tmp_path):
    logger, handler = make_logger(tmp_path)
    logger.info("parent.before")
    children = []
    for _ in range(2):
        pid = os.fork()
        if pid == 0:
            logger.info("child.event")
            os._exit(0)
        children.append(pid)
    for pid in children:
        assert os.waitpid(pid, 0)[1] == 0
    logger.info("parent.after")
    restarted, other = make_logger(tmp_path)
    restarted.info("restart.event")
    assert handler.writer != other.writer
    assert len(list(tmp_path.rglob("*.log"))) == 4
    assert len(records(tmp_path)) == 5


async def test_retention_stops_promptly(tmp_path):
    stop = asyncio.Event()
    task = asyncio.create_task(log_archive.run_retention(tmp_path, 30, stop))
    await asyncio.sleep(0)
    stop.set()
    await asyncio.wait_for(task, 2)
