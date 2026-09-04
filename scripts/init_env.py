"""Create a private, fresh Compose environment without printing or rotating secrets."""

from __future__ import annotations

import argparse
import base64
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _dotenv_value(value: str) -> str:
    if any(character in value for character in "\r\n\x00"):
        raise ValueError("Environment values cannot contain line breaks or NUL")
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def create_environment(output: Path, *, production: bool = False) -> None:
    """Use exclusive creation: an existing installation's keys must never be replaced."""
    template = (ROOT / ".env.example").read_text(encoding="utf-8")
    resolved_output = output.resolve()
    try:
        control_plane_env_file = os.path.relpath(resolved_output, ROOT / "infra").replace(
            os.sep, "/"
        )
    except ValueError:
        control_plane_env_file = resolved_output.as_posix()
    password = secrets.token_urlsafe(32)
    values = {
        "ENV": "production" if production else "development",
        "MCPLICA_VERSION": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "CONTROL_PLANE_ENV_FILE": control_plane_env_file,
        "POSTGRES_PASSWORD": password,
        "DATABASE_URL": f"postgresql+psycopg://mcplica:{password}@postgres:5432/mcplica",
        "MINIO_ROOT_USER": "mcplica-" + secrets.token_hex(8),
        "MINIO_ROOT_PASSWORD": secrets.token_urlsafe(32),
        "SECRET_ENCRYPTION_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
        "AUTH_SIGNING_KEY": secrets.token_urlsafe(64),
        "REFRESH_TOKEN_PEPPER": secrets.token_urlsafe(64),
        "BOOTSTRAP_SECRET": secrets.token_urlsafe(48),
        "METRICS_BEARER_TOKEN": secrets.token_urlsafe(48),
        "DEFAULT_ADMIN_EMAIL": "" if production else "admin@example.com",
        "DEFAULT_ADMIN_PASSWORD": "" if production else secrets.token_urlsafe(24),
        "RUNTIME_HOST_ROOT": str(resolved_output.parent / ".runtime"),
    }
    socket = Path("/var/run/docker.sock")
    if socket.exists():
        values["DOCKER_GID"] = str(socket.stat().st_gid)
    if production:
        values.update(
            TRAEFIK_TLS="true",
            TRAEFIK_ENTRYPOINT="websecure",
            TRAEFIK_CERT_RESOLVER="letsencrypt",
            BACKEND_IMAGE="",
            FRONTEND_IMAGE="",
            MCP_RUNTIME_IMAGE="",
        )
    seen: set[str] = set()
    lines: list[str] = []
    for line in template.splitlines():
        if line and not line.startswith("#") and "=" in line:
            key = line.split("=", 1)[0]
            if key in seen:
                raise ValueError(f"Duplicate environment variable in template: {key}")
            seen.add(key)
            if key in values:
                line = f"{key}={_dotenv_value(values[key])}"
        lines.append(line)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".env")
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()
    try:
        create_environment(args.output, production=args.production)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Environment was not replaced: {exc}\n")
    print(f"Created {args.output}; values are private and were not printed.")
    if args.production:
        print("Set public domains, HTTPS frontend origin, ACME email, and release image digests.")
        print("Use the production Compose override and the interactive administrator bootstrap.")
    else:
        print("Development sign-in credentials are DEFAULT_ADMIN_EMAIL/PASSWORD in that file.")
    print("Keep the encryption key with your encrypted backups. Never commit this file.")


if __name__ == "__main__":
    main()
