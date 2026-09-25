"""Opt-in Linux acceptance, ONLY on a fresh disposable Redis named ``redis``.

Run in a disposable backend image container on an isolated Docker network with
an empty Redis container, no published ports, and no application volumes or env
file. Set RUN_RQ_REGISTRATION_INTEGRATION=1. Mount backend and infra read-only at
/source/backend and /source/infra. Worker subprocesses receive the tests package
parent on PYTHONPATH to import the job. This suite deletes registration fields.
"""

import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from redis import Redis
from redis.exceptions import ConnectionError
from rq import Queue, Worker

from app.jobs.rq_worker import RegistrationRecoveringWorker

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_RQ_REGISTRATION_INTEGRATION") != "1" or sys.platform != "linux",
    reason="requires explicitly enabled disposable Linux/Redis environment",
)


def record_execution(counter: str, release: str) -> int:
    connection = Redis.from_url("redis://redis:6379/0")
    count = connection.incr(counter)
    deadline = time.monotonic() + 80
    while not connection.exists(release):
        if time.monotonic() > deadline:
            raise TimeoutError("test did not release job")
        time.sleep(0.1)
    return count


def wait_until(predicate, *, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError("condition did not become true before deadline")


def test_both_workers_recover_without_restart_or_job_reexecution(tmp_path):
    connection = Redis.from_url("redis://redis:6379/0", socket_timeout=5)
    assert connection.ping()
    root = Path(__file__).resolve().parents[3]
    services = yaml.safe_load((root / "infra/compose.yaml").read_text())["services"]
    token = uuid4().hex
    running = []
    try:
        for service, variable in (
            ("builder-worker", "BUILD_QUEUE_NAME"),
            ("deployment-worker", "DEPLOYMENT_QUEUE_NAME"),
        ):
            queue = f"mcp001-{service}-{token}"
            name = f"mcp001-{service}-{token}"
            command = services[service]["command"][:-1] + ["--name", name, queue]
            if service == "deployment-worker":
                # Run the actual supervisor with only its database/Docker route
                # reconciliation replaced. No persistent services are accessed.
                bootstrap = (
                    "import app.jobs.deployment_worker as d; "
                    "from unittest.mock import AsyncMock; "
                    "d._reconcile = AsyncMock(return_value="
                    "d.RouteReconciliationResult(0, 0, 0, 0)); d.main()"
                )
                command = [sys.executable, "-c", bootstrap, *command[3:]]
            env = {
                **os.environ,
                variable: queue,
                # Pytest imports this module as integration.test_rq_registration_recovery.
                # Its sys.path changes are not inherited by an RQ subprocess.
                "PYTHONPATH": os.pathsep.join(
                    (str(Path(__file__).resolve().parents[1]), os.getenv("PYTHONPATH", ""))
                ),
            }
            output = (tmp_path / f"{service}.log").open("w")
            process = subprocess.Popen(
                command, env=env, stdout=output, stderr=subprocess.STDOUT, start_new_session=True
            )
            item = dict(
                service=service,
                queue=queue,
                name=name,
                key=f"rq:worker:{name}",
                process=process,
                output=output,
                env=env,
            )
            running.append(item)
            wait_until(lambda item=item: connection.hexists(item["key"], "hostname"), timeout=20)
            item["pid"] = int(connection.hget(item["key"], "pid"))
            item["birth"] = connection.hget(item["key"], "birth")
            item["start"] = Path(f"/proc/{item['pid']}/stat").read_text().split()[21]

        def healthy(item):
            command = services[item["service"]]["healthcheck"]["test"][1:]
            return subprocess.run(command, env=item["env"], timeout=5, check=False).returncode

        def same_worker(item):
            assert item["process"].poll() is None
            assert connection.hget(item["key"], "pid") == str(item["pid"]).encode()
            assert connection.hget(item["key"], "birth") == item["birth"]
            assert Path(f"/proc/{item['pid']}/stat").read_text().split()[21] == item["start"]
            assert item["key"].encode() in connection.smembers("rq:workers")

        for item in running:
            assert healthy(item) == 0
            # --with-scheduler should have started a child before any jobs exist.
            children = Path(f"/proc/{item['pid']}/task/{item['pid']}/children")
            wait_until(lambda children=children: bool(children.read_text().strip()), timeout=10)

        for missing in (("hostname",), ("queues",), ("hostname", "queues"), ("hostname", "queues")):
            for item in running:
                connection.hdel(item["key"], *missing)
                assert healthy(item) == 1
            started = time.monotonic()
            wait_until(
                lambda missing=missing: all(
                    connection.hexists(item["key"], field) for item in running for field in missing
                )
            )
            for item in running:
                same_worker(item)
                assert healthy(item) == 0
            print(f"idle recovery {missing}: {time.monotonic() - started:.1f}s, both workers")

        for item in running:
            item["counter"] = f"mcp001:counter:{item['name']}"
            item["release"] = f"mcp001:release:{item['name']}"
            item["job"] = Queue(item["queue"], connection=connection).enqueue(
                record_execution, item["counter"], item["release"], job_timeout=90
            )
        wait_until(lambda: all(connection.get(item["counter"]) == b"1" for item in running))
        for item in running:
            connection.hdel(item["key"], "hostname", "queues")
            assert healthy(item) == 1
        started = time.monotonic()
        wait_until(
            lambda: all(
                connection.hget(item["key"], "hostname") == socket.gethostname().encode()
                and connection.hget(item["key"], "queues") == item["queue"].encode()
                for item in running
            )
        )
        print(f"busy recovery: {time.monotonic() - started:.1f}s, both workers")
        for item in running:
            same_worker(item)
            assert healthy(item) == 0
            connection.set(item["release"], "1")
        wait_until(lambda: all(item["job"].get_status() == "finished" for item in running))
        for item in running:
            assert item["job"].return_value() == 1
            assert connection.get(item["counter"]) == b"1"
            assert Queue(item["queue"], connection=connection).count == 0
            assert item["job"].get_executions() == []
            worker = Worker.find_by_key(item["key"], connection=connection)
            assert worker.successful_job_count == 1
            assert worker.failed_job_count == 0
            item["process"].terminate()
            assert item["process"].wait(timeout=15) == 0
            assert healthy(item) == 1
            assert item["key"].encode() not in connection.smembers("rq:workers")
            assert connection.hexists(item["key"], "death")
        print("jobs completed once; scheduler started; graceful shutdown unregistered both workers")
    except BaseException:
        for item in running:
            item["output"].flush()
            print(f"{item['service']} test log:\n{Path(item['output'].name).read_text()}")
        raise
    finally:
        for item in running:
            # Each test process has its own session, including scheduler/horse.
            with suppress(ProcessLookupError):
                os.killpg(item["process"].pid, signal.SIGKILL)
            item["process"].wait(timeout=10)
            item["output"].close()


def test_dead_worker_is_not_repaired(tmp_path):
    connection = Redis.from_url("redis://redis:6379/0", socket_timeout=5)
    name = f"mcp001-dead-{uuid4().hex}"
    key = f"rq:worker:{name}"
    with (tmp_path / "dead-worker.log").open("w") as output:
        process = subprocess.Popen(
            [
                "rq",
                "worker",
                "--worker-class",
                "app.jobs.rq_worker.RegistrationRecoveringWorker",
                "--with-scheduler",
                "--url",
                "redis://redis:6379/0",
                "--name",
                name,
                name,
            ],
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            wait_until(lambda: connection.hexists(key, "hostname"), timeout=20)
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
            connection.hdel(key, "hostname", "queues")
            heartbeat = connection.hget(key, "last_heartbeat")
            ttl = connection.ttl(key)
            # Observe beyond the repair interval; there is no independent writer.
            deadline = time.monotonic() + 32
            while time.monotonic() < deadline:
                assert not connection.hexists(key, "hostname")
                assert not connection.hexists(key, "queues")
                assert connection.hget(key, "last_heartbeat") == heartbeat
                time.sleep(0.2)
            assert connection.ttl(key) < ttl
        finally:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)


def test_unreachable_redis_heartbeat_fails_visibly():
    connection = Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2)
    worker = RegistrationRecoveringWorker([], connection=connection, prepare_for_work=False)
    with pytest.raises(ConnectionError):
        worker.heartbeat()
