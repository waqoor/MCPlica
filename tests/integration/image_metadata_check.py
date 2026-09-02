"""Verify release-relevant metadata on images built by canonical Compose."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = Path(os.getenv("MCPLICA_ENV_FILE", ".env"))
if not ENV_FILE.is_absolute():
    ENV_FILE = ROOT / ENV_FILE
COMPOSE = ["docker", "compose", "--env-file", str(ENV_FILE), "-f", "infra/compose.yaml"]
EXPECTED_USERS = {
    "api": "10001:10001",
    "runtime-validator": "10001:10001",
    "frontend": "101:101",
}


def _run(*arguments: str) -> str:
    result = subprocess.run(
        list(arguments),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return result.stdout


def main() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    compose = cast(
        dict[str, object],
        json.loads(_run(*COMPOSE, "config", "--format", "json")),
    )
    services = cast(dict[str, dict[str, object]], compose["services"])
    checked: list[str] = []
    for service, expected_user in EXPECTED_USERS.items():
        image = str(services[service]["image"])
        inspected = cast(
            list[dict[str, object]],
            json.loads(_run("docker", "image", "inspect", image)),
        )[0]
        config = cast(dict[str, object], inspected["Config"])
        labels = cast(dict[str, str], config.get("Labels") or {})
        expected_labels = {
            "org.opencontainers.image.version": version,
            "org.opencontainers.image.source": "https://github.com/yazeedhasan97/MCPlica",
            "org.opencontainers.image.licenses": "AGPL-3.0-only",
        }
        for key, expected in expected_labels.items():
            if labels.get(key) != expected:
                raise RuntimeError(f"{image} label {key} does not equal {expected!r}")
        if not labels.get("org.opencontainers.image.revision"):
            raise RuntimeError(f"{image} has no OCI source revision")
        if config.get("User") != expected_user:
            raise RuntimeError(
                f"{image} runs as {config.get('User')!r}, expected {expected_user!r}"
            )
        if service == "runtime-validator" and f"MCP_RUNTIME_VERSION={version}" not in cast(
            list[str], config.get("Env") or []
        ):
            raise RuntimeError(f"{image} does not embed runtime version {version}")
        checked.append(f"{service}={image}")
    print(f"Image metadata is release-consistent for {version}: {', '.join(checked)}")


if __name__ == "__main__":
    main()
