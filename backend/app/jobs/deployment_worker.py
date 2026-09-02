import asyncio
import logging
import signal
import sys

from app.clients.database import DatabaseClient
from app.clients.docker import DockerClient
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.repositories.deployments import DeploymentRepository
from app.services.deployment.route_reconciler import (
    RouteReconciliationResult,
    reconcile_active_runtime_routes,
)
from app.services.deployment.runtime_manager import RuntimeManager

logger = logging.getLogger("mcplica.deployment.worker")


async def _reconcile(settings: Settings) -> RouteReconciliationResult:
    database = DatabaseClient(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout_seconds=settings.database_pool_timeout_seconds,
    )
    docker = await DockerClient.connect(settings.docker_base_url)
    try:
        async with database.session() as session:
            return await reconcile_active_runtime_routes(
                session,
                DeploymentRepository(),
                RuntimeManager(docker, settings),
            )
    finally:
        await asyncio.gather(docker.close(), database.close())


def _log_reconciliation(result: RouteReconciliationResult) -> None:
    logger.info(
        "runtime_route_reconciliation_complete",
        extra={
            "candidates": result.candidates,
            "restored": result.restored,
            "skipped": result.skipped,
            "failed": result.failed,
        },
    )


async def _reconcile_periodically(settings: Settings, stopping: asyncio.Event) -> None:
    while not stopping.is_set():
        try:
            await asyncio.wait_for(
                stopping.wait(),
                timeout=settings.runtime_route_reconcile_interval_seconds,
            )
            return
        except TimeoutError:
            pass
        try:
            _log_reconciliation(await _reconcile(settings))
        except Exception:
            logger.exception("runtime_route_reconciliation_cycle_failed")


async def _stop_worker(
    worker: asyncio.subprocess.Process,
    *,
    timeout_seconds: float,
) -> int:
    if worker.returncode is not None:
        return worker.returncode
    worker.terminate()
    try:
        return await asyncio.wait_for(worker.wait(), timeout=timeout_seconds)
    except TimeoutError:
        worker.kill()
        return await worker.wait()


async def _supervise_worker(settings: Settings, worker_args: list[str]) -> int:
    _log_reconciliation(await _reconcile(settings))
    worker = await asyncio.create_subprocess_exec("rq", "worker", *worker_args)
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    registered_signals: list[signal.Signals] = []
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stopping.set)
        except NotImplementedError:  # pragma: no cover - entrypoint runs in Linux
            continue
        registered_signals.append(signum)

    periodic = asyncio.create_task(_reconcile_periodically(settings, stopping))
    worker_wait = asyncio.create_task(worker.wait())
    stop_wait = asyncio.create_task(stopping.wait())
    try:
        done, _ = await asyncio.wait(
            {worker_wait, stop_wait},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if worker_wait in done:
            return worker_wait.result()
        return await _stop_worker(
            worker,
            timeout_seconds=settings.shutdown_timeout_seconds,
        )
    finally:
        stopping.set()
        if not periodic.done():
            periodic.cancel()
        await asyncio.gather(periodic, return_exceptions=True)
        for pending in (worker_wait, stop_wait):
            if not pending.done():
                pending.cancel()
        await asyncio.gather(worker_wait, stop_wait, return_exceptions=True)
        for signum in registered_signals:
            loop.remove_signal_handler(signum)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.is_production)
    try:
        return_code = asyncio.run(_supervise_worker(settings, sys.argv[1:]))
    except Exception:
        logger.exception("deployment_worker_supervisor_failed")
        raise SystemExit(1) from None
    raise SystemExit(return_code)


if __name__ == "__main__":
    main()
