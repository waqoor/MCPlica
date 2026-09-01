"""Prepare a NEW disposable local Compose installation for full-stack acceptance.

Never run against an existing deployment. Refuses to replace .env; only external
OpenRouter and upstream API boundaries use fixtures. Application images/topology
remain the canonical infra/compose.yaml implementation.
"""

import ipaddress
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    result = subprocess.run(
        [
            "docker", "network", "inspect", "bridge", "--format",
            "{{(index .IPAM.Config 0).Gateway}}",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    gateway = str(ipaddress.IPv4Address(result.stdout.strip()))
    subprocess.run([sys.executable, str(ROOT / "scripts/init_env.py")], check=True, timeout=15)
    values = {
        "BACKEND_IMAGE": "mcplica/backend:test",
        "FRONTEND_IMAGE": "mcplica/frontend:test",
        "MCP_RUNTIME_IMAGE": "mcplica/runtime:test",
        "MCP_RUNTIME_PULL_POLICY": "never",
        "OPENROUTER_API_KEY": "fixture-not-a-real-provider-key",
        "OPENROUTER_BASE_URL": f"http://{gateway}:9010/api/v1",
        "RUNTIME_ALLOWED_DEVELOPMENT_HOSTS": gateway,
    }
    target = ROOT / ".env"
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
