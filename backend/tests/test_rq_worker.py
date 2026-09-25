import os
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from redis import Redis
from redis.exceptions import ConnectionError
from rq import Worker
from rq.exceptions import DequeueTimeout
from rq.utils import now

from app.jobs.rq_worker import RegistrationRecoveringWorker


class RegistrationStore:
    """In-memory command executor; real redis-py pipelines and RQ lifecycle code.

    No network connection is used. This models only the commands under test,
    not Redis timing, transactions or a running worker process.
    """

    def __init__(self):
        self.hashes = {}
        self.sets = {}
        self.expiry = {}
        self.commands = []
        self.redis = Mock(spec=Redis)
        self.redis.connection_pool = Mock(connection_kwargs={})
        self.redis.client_list.return_value = []
        self.redis.pipeline.side_effect = self.pipeline
        self.redis.exists.side_effect = lambda key: key in self.hashes
        self.redis.hexists.side_effect = lambda key, field: field in self.hashes.get(key, {})
        self.redis.smembers.side_effect = lambda key: {
            value.encode() for value in self.sets.get(key, set())
        }
        self.redis.hgetall.side_effect = lambda key: {
            field.encode(): str(value).encode() for field, value in self.hashes.get(key, {}).items()
        }
        for method in ("hset", "hsetnx", "expire"):
            getattr(self.redis, method).side_effect = lambda *args, command=method: self.execute(
                (command.upper(), *args)
            )

    def execute(self, command):
        self.commands.append(command)
        operation, key, *args = command
        if operation == "DEL":
            return int(self.hashes.pop(key, None) is not None)
        if operation == "EXPIRE":
            self.expiry[key] = args[0]
            return int(key in self.hashes)
        if operation in ("SADD", "SREM"):
            members = self.sets.setdefault(key, set())
            before = len(members)
            if operation == "SADD":
                members.update(args)
            else:
                members.difference_update(args)
            return abs(len(members) - before)
        assert operation in ("HSET", "HSETNX"), command
        values = self.hashes.setdefault(key, {})
        added = 0
        for field, value in zip(args[::2], args[1::2], strict=True):
            missing = field not in values
            added += missing
            if missing or operation == "HSET":
                values[field] = value
        return added

    def pipeline(self):
        pipeline = Redis().pipeline()

        def execute():
            commands = list(pipeline.command_stack)
            pipeline.reset()
            return [self.execute(args) for args, _ in commands]

        pipeline.execute = Mock(side_effect=execute)
        return pipeline


@pytest.fixture
def store():
    return RegistrationStore()


@pytest.fixture
def worker(store):
    worker = RegistrationRecoveringWorker(["mcplica-builds", "secondary"], connection=store.redis)
    worker.register_birth()
    store.commands.clear()
    return worker


@pytest.mark.parametrize("missing", [("hostname",), ("queues",), ("hostname", "queues")])
@pytest.mark.parametrize("pipelined", [False, True])
def test_repeated_loss_repairs_only_missing_fields(store, worker, missing, pipelined):
    values = store.hashes[worker.key]
    values.update(current_job="job-1", successful_job_count=7, state="busy")
    identity = worker.pid, worker.name
    for _ in range(2):
        before = values.copy()
        for field in missing:
            del values[field]
        if pipelined:
            pipeline = store.pipeline()
            worker.heartbeat(pipeline=pipeline)
            assert all(field not in values for field in missing)
            pipeline.execute.assert_not_called()
            pipeline.execute()
        else:
            worker.heartbeat()
        assert {k: v for k, v in values.items() if k != "last_heartbeat"} == {
            k: v for k, v in before.items() if k != "last_heartbeat"
        }
        assert (worker.pid, worker.name) == identity
        assert store.expiry[worker.key] == worker.worker_ttl + 60
    assert {command[0] for command in store.commands} == {"HSET", "EXPIRE", "HSETNX"}


def test_heartbeat_preserves_existing_metadata_and_other_workers(store, worker):
    store.hashes[worker.key].update(hostname="existing-host", queues="existing-queue")
    store.hashes["rq:worker:other"] = {"last_heartbeat": "unchanged"}
    before = deepcopy(store.hashes)
    worker.heartbeat(timeout=91)
    assert store.hashes[worker.key]["hostname"] == "existing-host"
    assert store.hashes[worker.key]["queues"] == "existing-queue"
    assert store.hashes["rq:worker:other"] == before["rq:worker:other"]
    assert store.expiry[worker.key] == 91


def test_caller_pipeline_keeps_upstream_result_positions(store, worker):
    del store.hashes[worker.key]["queues"]
    pipeline = store.pipeline()
    worker.heartbeat(timeout=90, pipeline=pipeline)
    assert [args[0] for args, _ in pipeline.command_stack] == ["HSET", "EXPIRE", "HSETNX", "HSETNX"]
    pipeline.execute.assert_not_called()
    assert pipeline.execute() == [0, 1, 0, 1]


def test_caller_pipeline_preserves_preexisting_commands(store, worker):
    pipeline = store.pipeline()
    pipeline.hset("unrelated", "value", "kept")
    worker.heartbeat(pipeline=pipeline)
    assert "unrelated" not in store.hashes
    assert pipeline.execute() == [1, 0, 1, 0, 0]
    assert store.hashes["unrelated"] == {"value": "kept"}


@pytest.mark.parametrize(
    "service, variable, queue",
    [
        ("builder-worker", "BUILD_QUEUE_NAME", "custom-builds"),
        ("deployment-worker", "DEPLOYMENT_QUEUE_NAME", "custom-deployments"),
    ],
)
@pytest.mark.parametrize("missing", [("hostname",), ("queues",), ("hostname", "queues")])
def test_exact_compose_healthcheck_recovers_repeatedly(
    store, monkeypatch, service, variable, queue, missing
):
    root = Path(__file__).resolve().parents[2]
    services = yaml.safe_load((root / "infra/compose.yaml").read_text())["services"]
    check = services[service]["healthcheck"]["test"]
    assert check[:3] == ["CMD", "python", "-c"]
    monkeypatch.setenv(variable, queue)
    monkeypatch.setattr(Redis, "from_url", lambda url: store.redis)
    worker = RegistrationRecoveringWorker([queue], connection=store.redis)
    worker.register_birth()
    identity = worker.pid, worker.name

    def health_exit():
        with pytest.raises(SystemExit) as result:
            exec(check[3], {})
        return result.value.code

    assert health_exit() == 0
    for _ in range(2):
        for field in missing:
            del store.hashes[worker.key][field]
        assert health_exit() == 1
        worker.heartbeat()
        assert health_exit() == 0
        assert (worker.pid, worker.name) == identity
    worker.register_death()
    assert health_exit() == 1


@pytest.mark.parametrize("worker_hash_missing", [False, True])
@pytest.mark.parametrize("job_hash_missing", [False, True])
def test_rq_maintain_heartbeats_preserves_worker_and_job_recovery(
    store, worker, worker_hash_missing, job_hash_missing
):
    if worker_hash_missing:
        del store.hashes[worker.key]
    else:
        del store.hashes[worker.key]["hostname"]
    job = Mock(key="rq:job:example", timeout=300)
    if not job_hash_missing:
        store.hashes[job.key] = {"last_heartbeat": "old", "status": "started"}
    job.heartbeat.side_effect = lambda timestamp, ttl, pipeline, xx: pipeline.hset(
        job.key, "last_heartbeat", str(timestamp)
    )
    worker.execution = Mock()
    worker.execution.heartbeat.side_effect = lambda registry, ttl, pipeline: pipeline.hset(
        "execution", "last_heartbeat", "new"
    )

    worker.maintain_heartbeats(job)

    assert store.hashes[worker.key]["hostname"] == worker.hostname
    assert store.expiry[worker.key] == worker.job_monitoring_interval + 60
    assert (job.key not in store.hashes) == job_hash_missing
    if not job_hash_missing:
        assert store.hashes[job.key]["status"] == "started"
    # RQ must still detect an expired worker using result zero, not an HSETNX result.
    assert ("birth" in store.hashes[worker.key]) is True
    assert sum(cmd[0] == "HSET" and "birth" in cmd for cmd in store.commands) == int(
        worker_hash_missing
    )


@pytest.mark.parametrize("kind", ["inspection", "horse", "different_pid", "unregistered"])
def test_only_registered_owning_parent_repairs(store, worker, monkeypatch, kind):
    if kind in ("inspection", "unregistered"):
        worker = RegistrationRecoveringWorker(
            ["mcplica-builds"],
            connection=store.redis,
            prepare_for_work=kind != "inspection",
        )
        # A reconstructed object's pid/hostname can match the live process.
        worker.pid = os.getpid()
        worker.hostname = "host"
    elif kind == "horse":
        worker._is_horse = True
    else:
        monkeypatch.setattr("app.jobs.rq_worker.os.getpid", lambda: worker.pid + 1)
    store.commands.clear()
    worker.heartbeat()
    assert not any(command[0] == "HSETNX" for command in store.commands)


def test_death_disables_repair_even_if_registration_death_fails(store, worker):
    store.redis.pipeline.side_effect = ConnectionError("Redis unavailable")
    with pytest.raises(ConnectionError):
        worker.register_death()
    store.redis.pipeline.side_effect = store.pipeline
    store.commands.clear()
    worker.heartbeat()
    assert not any(command[0] == "HSETNX" for command in store.commands)


def test_shutdown_unregisters_and_does_not_repair_again(store, worker):
    worker.register_death()
    assert worker.key not in store.sets["rq:workers"]
    assert store.expiry[worker.key] == 60
    del store.hashes[worker.key]["hostname"]
    store.commands.clear()
    worker.heartbeat()
    assert "hostname" not in store.hashes[worker.key]
    assert not any(command[0] == "HSETNX" for command in store.commands)


@pytest.mark.parametrize("pipelined", [False, True])
def test_redis_errors_are_not_swallowed(store, worker, pipelined):
    pipeline = store.pipeline()
    pipeline.execute.side_effect = ConnectionError("Redis unavailable")
    store.redis.pipeline.side_effect = lambda: pipeline
    with pytest.raises(ConnectionError, match="Redis unavailable"):
        if pipelined:
            worker.heartbeat(pipeline=pipeline)
            pipeline.execute()
        else:
            worker.heartbeat()


@pytest.mark.parametrize("ttl, expected", [(420, 30), (30, 15), (10, 1)])
def test_idle_bound_preserves_worker_ttl(store, ttl, expected):
    worker = RegistrationRecoveringWorker([], connection=store.redis, worker_ttl=ttl)
    assert worker.dequeue_timeout == expected
    assert worker.worker_ttl == ttl


def test_idle_dequeue_timeout_reenters_repair_without_restarting(store, worker, monkeypatch):
    worker.last_cleaned_at = now()
    calls = 0

    def dequeue(queues, timeout, **kwargs):
        nonlocal calls
        assert timeout == 30
        calls += 1
        if calls == 1:
            del store.hashes[worker.key]["hostname"]
            del store.hashes[worker.key]["queues"]
            raise DequeueTimeout()
        assert store.hashes[worker.key]["hostname"] == worker.hostname
        assert store.hashes[worker.key]["queues"] == "mcplica-builds,secondary"
        return None

    monkeypatch.setattr(worker.queue_class, "dequeue_any", dequeue)
    monkeypatch.setattr(worker, "set_state", Mock())
    assert worker.dequeue_job_and_maintain_ttl(worker.dequeue_timeout) is None
    assert calls == 2


def test_worker_keeps_rq_job_and_scheduler_implementations():
    for method in ("execute_job", "monitor_work_horse", "work", "_start_scheduler", "teardown"):
        assert getattr(RegistrationRecoveringWorker, method) is getattr(Worker, method)
