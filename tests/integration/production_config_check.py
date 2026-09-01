"""Validate resolved production Compose settings without starting production services.

Uses fresh temporary secrets and explicit synthetic image digests. This checks the
configuration contract, not registry availability, DNS, certificates, or deployment.
Run with the backend environment and PYTHONPATH=backend.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from dotenv import dotenv_values

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]
CONTROL_PLANE = ("migrate", "api", "builder-worker", "deployment-worker")


def main() -> None:
    with TemporaryDirectory(prefix="mcplica-production-config-") as directory:
        environment_file = Path(directory) / ".env"
        subprocess.run(
            [sys.executable, "scripts/init_env.py", "--production", "--output", str(environment_file)],
            cwd=ROOT,
            capture_output=True,
            check=True,
            timeout=15,
        )
        environment = os.environ.copy()
        # Do not let this runner's development settings override the isolated file.
        for name in dotenv_values(environment_file):
            environment.pop(name, None)
        environment.update(
            MCPLICA_ENV_FILE=str(environment_file),
            BACKEND_IMAGE="mcplica/backend@sha256:" + "a" * 64,
            FRONTEND_IMAGE="mcplica/frontend@sha256:" + "b" * 64,
            MCP_RUNTIME_IMAGE="mcplica/runtime@sha256:" + "c" * 64,
            UI_DOMAIN="ui.example.com",
            API_DOMAIN="api.example.com",
            MCP_DOMAIN="mcp.example.com",
            ACME_EMAIL="operator@example.com",
            # Shell overrides must reach producers, consumers and mount targets.
            BUILD_QUEUE_NAME="config-check-builds",
            DEPLOYMENT_QUEUE_NAME="config-check-deployments",
            RUNTIME_WORKER_ROOT="/config-check-runtime",
            TRAEFIK_NETWORK="mcplica-config-check-edge",
        )
        command = [
            "docker", "compose", "--env-file", str(environment_file),
            "-f", "infra/compose.yaml", "-f", "infra/compose.production.yaml",
            "config", "--format", "json",
        ]
        result = subprocess.run(
            command, cwd=ROOT, env=environment, capture_output=True,
            text=True, check=True, timeout=30,
        )
        model = json.loads(result.stdout)
        services = model["services"]
        for name in CONTROL_PLANE:
            values = services[name]["environment"]
            with patch.dict(os.environ, {key: str(value) for key, value in values.items()}, clear=True):
                settings = Settings(_env_file=None)
            assert settings.is_production, name
            assert settings.traefik_tls and settings.traefik_entrypoint == "websecure", name
            assert settings.frontend_origin == "https://ui.example.com", name
            assert settings.api_domain == "api.example.com", name
            assert settings.mcp_domain == "mcp.example.com", name
            assert settings.build_queue_name == "config-check-builds", name
            assert settings.deployment_queue_name == "config-check-deployments", name
            assert settings.runtime_worker_root == "/config-check-runtime", name
            assert settings.default_admin_email is None, name
            assert settings.default_admin_password is None, name
            assert services[name].get("build") is None, name
        for name in ("builder-worker", "deployment-worker"):
            queue = "BUILD_QUEUE_NAME" if name == "builder-worker" else "DEPLOYMENT_QUEUE_NAME"
            assert services[name]["command"][-1] == environment[queue], name
        for name in ("runtime-init", "deployment-worker"):
            mounts = services[name]["volumes"]
            assert any(mount["target"] == "/config-check-runtime" for mount in mounts), name
        assert set(services["runtime-init"]["environment"]) == {
            "RUNTIME_UID", "RUNTIME_GID", "RUNTIME_WORKER_ROOT",
        }
        assert model["networks"]["edge"]["name"] == environment["TRAEFIK_NETWORK"]
        for name in ("api", "frontend"):
            assert services[name]["labels"]["traefik.docker.network"] == environment["TRAEFIK_NETWORK"]
        network_option = "--providers.docker.network=" + environment["TRAEFIK_NETWORK"]
        assert network_option in services["traefik"]["command"]
        edge_ports = services["traefik"]["ports"]
        assert sorted(int(port["published"]) for port in edge_ports) == [80, 443]
        assert all(port.get("host_ip", "0.0.0.0") in ("", "0.0.0.0") for port in edge_ports)
        for name in ("postgres", "redis", "milvus", "etcd", "minio"):
            assert not services[name].get("ports"), name
        # Required release identifiers must fail closed; never start with a local tag.
        environment.pop("MCP_RUNTIME_IMAGE")
        missing_image = subprocess.run(
            command, cwd=ROOT, env=environment, capture_output=True, timeout=30,
        )
        assert missing_image.returncode != 0, "missing release image did not fail closed"
    print("Production Compose settings validated for all four control-plane processes.")
    print("TLS/ports, queue and mount overrides, secret isolation, and missing-image rejection passed.")


if __name__ == "__main__":
    main()
