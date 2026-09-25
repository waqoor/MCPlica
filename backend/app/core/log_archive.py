"""Private Linux archive: descriptor-relative traversal never follows symlinks.

Each process writes its own segments. No descriptor survives an emission/fork.
The root must be on a local filesystem, owned by the control-plane user.
"""

import asyncio
import errno
import json
import logging
import os
import re
import stat
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager, suppress
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

_SERVICE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_SEGMENT = re.compile(r"^[0-9]+-[0-9a-f]{32}\.[0-9]+\.log$")


def utc_today() -> date:
    return datetime.now(UTC).date()


def report_failure(event: str) -> None:
    # Never include exception text, paths, or the failed record; never recurse.
    with suppress(Exception):
        sys.stderr.write('{"level":"error","message":"' + event + '"}\n')


@contextmanager
def directory(root: Path, parts: tuple[str, ...] = (), *, create: bool = False) -> Generator[int]:
    if os.name != "posix":
        raise OSError("secure archive requires POSIX directory descriptors")
    if not root.is_absolute() or root == Path("/") or ".." in root.parts:
        raise ValueError("archive root must be an absolute non-root path")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open("/", flags)
    try:
        for part in (*root.parts[1:], *parts):
            if part in ("", ".", "..") or "/" in part or "\\" in part:
                raise ValueError("invalid archive component")
            if create:
                with suppress(FileExistsError):
                    os.mkdir(part, mode=0o700, dir_fd=descriptor)
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


class ArchiveHandler(logging.Handler):
    def __init__(self, root: Path, max_bytes: int) -> None:
        super().__init__()
        if max_bytes < 1024:
            raise ValueError("log segment limit must be at least 1024 bytes")
        self.root = root
        self.max_bytes = max_bytes
        self._pid = os.getpid()
        self.writer = f"{self._pid}-{uuid4().hex}"
        self._last_failure = float("-inf")
        self.failures = 0
        self._segment_path: tuple[str, ...] = ()
        self._segment = 0

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if os.name != "posix":
                raise OSError("secure archive requires POSIX directory descriptors")
            if os.getpid() != self._pid:
                self._pid = os.getpid()
                self.writer = f"{self._pid}-{uuid4().hex}"
                self._segment_path = ()
            # Filter supplies this private tuple from trusted scoped context only.
            target = getattr(record, "_archive_build", None)
            if target is not None:
                project, build = target
                parts = ("projects", str(UUID(project)), str(UUID(build)))
            else:
                service = getattr(record, "service", "mcplica")
                if not isinstance(service, str) or not _SERVICE.fullmatch(service):
                    service = "mcplica"
                parts = ("platform", service)
            parts = (*parts, utc_today().isoformat())
            data = (self.format(record) + "\n").encode("utf-8")
            if len(data) > min(self.max_bytes, 65536):
                original = json.loads(data)
                bounded = {
                    key: original[key]
                    for key in ("timestamp", "service", "scope", "project_id", "build_id")
                    if key in original
                }
                bounded.update(
                    level="warning", message="log.record_omitted", error_code="RECORD_TOO_LARGE"
                )
                data = (json.dumps(bounded, separators=(",", ":")) + "\n").encode("utf-8")
            with directory(self.root, parts, create=True) as parent:
                segment = self._segment if parts == self._segment_path else 0
                while True:
                    name = f"{self.writer}.{segment}.log"
                    fd = os.open(
                        name,
                        os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                        0o600,
                        dir_fd=parent,
                    )
                    try:
                        info = os.fstat(fd)
                        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                            raise OSError("unsafe archive file")
                        if info.st_size + len(data) <= self.max_bytes:
                            # One process owns this name; handler lock serializes threads.
                            view = memoryview(data)
                            while view:
                                written = os.write(fd, view)
                                if written == 0:
                                    raise OSError("incomplete archive write")
                                view = view[written:]
                            self._segment_path, self._segment = parts, segment
                            break
                    finally:
                        os.close(fd)
                    segment += 1
        except Exception:
            self.failures += 1
            now = time.monotonic()
            if now - self._last_failure >= 60:
                self._last_failure = now
                report_failure("log.archive_write_failed")


def _uuid(value: str) -> bool:
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def cleanup_logs(root: Path, retention_days: int = 30, *, today: date | None = None) -> int:
    """Keep today and the previous N-1 UTC dates. Ignore everything unrecognized."""
    removed = 0
    try:
        if retention_days < 1:
            raise ValueError("retention must be positive")
        cutoff = (today or utc_today()) - timedelta(days=retention_days - 1)

        def visit(parts: tuple[str, ...]) -> None:
            nonlocal removed
            with directory(root, parts) as parent:
                for name in os.listdir(parent):
                    info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode):
                        continue
                    depth = len(parts)
                    date_depth = 2 if parts and parts[0] == "platform" else 3
                    if depth == date_depth + 1:
                        if (
                            _SEGMENT.fullmatch(name)
                            and stat.S_ISREG(info.st_mode)
                            and info.st_nlink == 1
                            and date.fromisoformat(parts[-1]) < cutoff
                        ):
                            os.unlink(name, dir_fd=parent)
                            removed += 1
                        continue
                    if not stat.S_ISDIR(info.st_mode):
                        continue
                    if depth == 0:
                        valid = name in ("platform", "projects")
                    elif depth == date_depth:
                        try:
                            valid = (
                                date.fromisoformat(name).isoformat() == name
                                and date.fromisoformat(name) < cutoff
                            )
                        except ValueError:
                            valid = False
                    elif parts[0] == "platform":
                        valid = bool(_SERVICE.fullmatch(name))
                    else:
                        valid = _uuid(name)
                    if valid:
                        try:
                            visit((*parts, name))
                            os.rmdir(name, dir_fd=parent)  # Empty recognized directories only.
                        except FileNotFoundError:
                            pass
                        except OSError as exc:
                            # Nonempty directories are expected, other failures remain visible.
                            if exc.errno != errno.ENOTEMPTY:
                                raise

        visit(())
    except FileNotFoundError:
        pass
    except Exception:
        report_failure("log.retention_failed")
    return removed


async def run_retention(root: Path, retention_days: int, stop: asyncio.Event) -> None:
    while not stop.is_set():
        await asyncio.to_thread(cleanup_logs, root, retention_days)
        with suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=3600)
