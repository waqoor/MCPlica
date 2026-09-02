"""Prepare a NEW disposable local Compose installation for full-stack acceptance.

Never run against an existing deployment. Refuses to replace its selected output file; only external
OpenRouter and upstream API boundaries use fixtures. Application images/topology
remain the canonical infra/compose.yaml implementation.
"""

import argparse
import ipaddress
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".env")
    parser.add_argument("--project-name", default="mcplica")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=8080)
    parser.add_argument("--edge-tls-port", type=int, default=8443)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", args.project_name):
        parser.error(
            "--project-name must contain lowercase letters, digits, hyphens, or underscores"
        )
    for name in ("api_port", "frontend_port", "edge_tls_port"):
        if not 1 <= getattr(args, name) <= 65535:
            parser.error(f"--{name.replace('_', '-')} must be between 1 and 65535")
    result = subprocess.run(
        [
            "docker",
            "network",
            "inspect",
            "bridge",
            "--format",
            "{{(index .IPAM.Config 0).Gateway}}",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    gateway = (
        "host.docker.internal"
        if os.name == "nt"
        else str(ipaddress.IPv4Address(result.stdout.strip()))
    )
    target = args.output if args.output.is_absolute() else ROOT / args.output
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/init_env.py"), "--output", str(target)],
        check=True,
        timeout=15,
    )
    runtime_root_name = (
        ".runtime" if args.project_name == "mcplica" else f".runtime-{args.project_name}"
    )
    try:
        control_plane_env_file = os.path.relpath(target.resolve(), ROOT / "infra").replace(
            os.sep, "/"
        )
    except ValueError:
        control_plane_env_file = target.resolve().as_posix()
    values = {
        "COMPOSE_PROJECT_NAME": args.project_name,
        "CONTROL_PLANE_ENV_FILE": control_plane_env_file,
        "API_PORT": str(args.api_port),
        "FRONTEND_PORT": str(args.frontend_port),
        "EDGE_TLS_PORT": str(args.edge_tls_port),
        "BACKEND_IMAGE": "mcplica/backend:test",
        "FRONTEND_IMAGE": "mcplica/frontend:test",
        "MCP_RUNTIME_IMAGE": "mcplica/runtime:test",
        "MCP_RUNTIME_PULL_POLICY": "never",
        "BUILDER_NETWORK": f"{args.project_name}-builder",
        "EGRESS_NETWORK": f"{args.project_name}-egress",
        "TRAEFIK_NETWORK": f"{args.project_name}-edge",
        "TRAEFIK_CONTAINER_NAME": f"{args.project_name}-traefik-1",
        "RUNTIME_HOST_ROOT": (ROOT / runtime_root_name).resolve().as_posix(),
        "OPENROUTER_API_KEY": "fixture-not-a-real-provider-key",
        "OPENROUTER_BASE_URL": f"http://{gateway}:9010/api/v1",
        "RUNTIME_ALLOWED_DEVELOPMENT_HOSTS": gateway,
    }
    lines = target.read_text().splitlines()
    for key, value in values.items():
        lines = [line for line in lines if not line.startswith(key + "=")]
        lines.append(f"{key}='{value}'")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    github_env = os.getenv("GITHUB_ENV")
    if github_env:
        with Path(github_env).open("a", encoding="utf-8") as handle:
            handle.write(f"E2E_UPSTREAM_BASE_URL=http://{gateway}:9009/api\n")
    else:
        print(f"Set E2E_UPSTREAM_BASE_URL=http://{gateway}:9009/api for the acceptance harness.")


if __name__ == "__main__":
    main()
