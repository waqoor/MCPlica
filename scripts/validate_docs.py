#!/usr/bin/env python3
"""Validate repository documentation links, environment names, and command invariants."""

from __future__ import annotations

import re
import subprocess
import sys
import urllib.parse
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
REFERENCE_LINK = re.compile(r"(?m)^\[[^\]]+\]:\s*(\S+)")
HTML_LINK = re.compile(r"(?:href|src)=[\"']([^\"']+)[\"']")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
ENV_TOKEN = re.compile(r"`(ENV|[A-Z][A-Z0-9]*_[A-Z0-9_*]+)`")
DOCUMENTED_EXTERNAL_ENV = {
    "BUILD_INPUTS_STALE",  # reason code, not an environment variable
    "CLA_STATUS_CONTEXT",
    "E2E_ADMIN_EMAIL",
    "E2E_ADMIN_PASSWORD",
    "E2E_API_BASE",
    "E2E_BASE_URL",
    "E2E_LIVE",
    "E2E_UPSTREAM_BASE_URL",
    "ENV_FILE",  # Makefile input, forwarded to MCPLICA_ENV_FILE
    "GH_TOKEN",
    "GITHUB_ACTOR",
    "GITHUB_ENV",
    "GITHUB_REF_NAME",
    "GITHUB_REPOSITORY",
    "GITHUB_RUN_ID",
    "GITHUB_SERVER_URL",
    "GITHUB_SHA",
    "MCP_RUNTIME_VERSION",  # internal/legacy name documented only for migration
    "MANIFEST_EXCEEDS_RUNTIME_LIMIT",  # reason code
    "MANIFEST_RUNTIME_SIZE_LIMIT_EXCEEDED",  # reason code
    "MCPLICA_ENV_FILE",
    "O_NOFOLLOW",  # operating-system flag
    "PROMETHEUS_MULTIPROC_DIR",
    "PYTHONPATH",
    "RUN_DOCKER_INTEGRATION",
    "RESPONSE_CONTRACT_INVALID",  # reason code
    "TEST_DATABASE_URL",
    "UV_PROJECT_ENVIRONMENT",
}
STALE_TRACKED_PATHS = {
    "docs/AGENT1_HANDOFF.md",
    "docs/AGENT2_HANDOFF.md",
    "docs/AGENT3_HANDOFF.md",
    "docs/STARTER_STATUS.md",
    "docs/evidence/agent1-backend-control-plane.md",
    "docs/evidence/agent2-runtime-deployment.md",
    "docs/evidence/agent3-requirement-traceability.md",
}


def _slug_headings(path: Path) -> set[str]:
    slugs: set[str] = set()
    occurrences: defaultdict[str, int] = defaultdict(int)
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING.match(line)
        if not match:
            continue
        value = re.sub(r"<[^>]+>", "", match.group(1).strip().lower())
        value = re.sub(r"[`*_~]", "", value)
        value = re.sub(r"[^\w\- ]", "", value, flags=re.UNICODE)
        base = re.sub(r"\s+", "-", value).strip("-")
        suffix = occurrences[base]
        occurrences[base] += 1
        slugs.add(base if suffix == 0 else f"{base}-{suffix}")
    return slugs


def _target_parts(raw: str) -> tuple[str, str]:
    value = raw.strip().strip("<>")
    if ' "' in value or " '" in value:
        value = value.split(" ", 1)[0]
    parsed = urllib.parse.urlsplit(value)
    return urllib.parse.unquote(parsed.path), urllib.parse.unquote(parsed.fragment)


def validate_links(markdown_files: list[Path]) -> list[str]:
    errors: list[str] = []
    heading_cache: dict[Path, set[str]] = {}
    for source in markdown_files:
        text = source.read_text(encoding="utf-8")
        targets = [
            *MARKDOWN_LINK.findall(text),
            *REFERENCE_LINK.findall(text),
            *HTML_LINK.findall(text),
        ]
        for raw in targets:
            if raw.startswith(("http://", "https://", "mailto:", "data:")):
                continue
            path_value, fragment = _target_parts(raw)
            target = source if not path_value else (source.parent / path_value)
            try:
                target = target.resolve()
                target.relative_to(ROOT.resolve())
            except ValueError:
                errors.append(f"{source.relative_to(ROOT)} links outside the repository: {raw}")
                continue
            if not target.exists():
                errors.append(f"{source.relative_to(ROOT)} has missing local link: {raw}")
                continue
            if fragment and target.is_file() and target.suffix.lower() == ".md":
                headings = heading_cache.setdefault(target, _slug_headings(target))
                if fragment not in headings:
                    errors.append(
                        f"{source.relative_to(ROOT)} has missing heading #{fragment} in "
                        f"{target.relative_to(ROOT)}"
                    )
    return errors


def _environment_keys() -> set[str]:
    keys: set[str] = set()
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            name = line.split("=", 1)[0]
            if name in keys:
                raise ValueError(f"duplicate .env.example key: {name}")
            keys.add(name)
    return keys


def validate_environment(markdown_files: list[Path]) -> list[str]:
    errors: list[str] = []
    keys = _environment_keys()
    documented = set(DOCUMENTED_EXTERNAL_ENV)
    documented.update(keys)
    for source in markdown_files:
        for name in ENV_TOKEN.findall(source.read_text(encoding="utf-8")):
            if "*" not in name and name not in documented:
                errors.append(
                    f"{source.relative_to(ROOT)} documents unknown environment variable {name}"
                )

    compose_text = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in ("infra/compose.yaml", "infra/compose.production.yaml")
    )
    compose_names = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", compose_text))
    missing = compose_names - keys - {"MCPLICA_ENV_FILE"}
    if missing:
        errors.append(
            "Compose interpolates variables absent from .env.example: " + ", ".join(sorted(missing))
        )
    return errors


def validate_commands(markdown_files: list[Path]) -> list[str]:
    errors: list[str] = []
    for source in markdown_files:
        for line_number, line in enumerate(
            source.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped = line.strip()
            if (
                stripped.startswith("docker compose ")
                and stripped
                not in {
                    "docker compose version",
                    "docker compose --version",
                }
                and ("--env-file" not in stripped or "-f infra/compose.yaml" not in stripped)
            ):
                errors.append(
                    f"{source.relative_to(ROOT)}:{line_number} uses non-canonical "
                    "Docker Compose syntax"
                )
    deployment_files = [
        ROOT / "infra/compose.yaml",
        ROOT / "infra/compose.production.yaml",
        *sorted((ROOT / "infra/docker").glob("Dockerfile*")),
    ]
    for path in deployment_files:
        value = path.read_text(encoding="utf-8").lower()
        for forbidden in ("pytest", "playwright", "vitest", "pnpm test"):
            if forbidden in value:
                errors.append(f"deployment definition {path.relative_to(ROOT)} embeds {forbidden}")
    return errors


def validate_tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    tracked = set(result.stdout.decode("utf-8").split("\0"))
    errors = [
        f"stale review file is tracked: {path}" for path in sorted(STALE_TRACKED_PATHS & tracked)
    ]
    output_paths = sorted(path for path in tracked if path.startswith("output/"))
    if output_paths:
        errors.append(f"disposable output is tracked ({len(output_paths)} files under output/)")
    runtime_paths = sorted(
        path
        for path in tracked
        if path.startswith(".runtime/") or re.match(r"^\.runtime-[^/]+/", path)
    )
    if runtime_paths:
        errors.append(
            f"private runtime material is tracked ({len(runtime_paths)} files under .runtime*)"
        )
    return errors


def tracked_markdown_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.md"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return sorted(ROOT / path for path in result.stdout.decode("utf-8").split("\0") if path)


def main() -> int:
    try:
        markdown_files = tracked_markdown_files()
        errors = [
            *validate_links(markdown_files),
            *validate_environment(markdown_files),
            *validate_commands(markdown_files),
            *validate_tracked_files(),
        ]
    except (OSError, UnicodeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"documentation validation failed: {exc}", file=sys.stderr)
        return 1
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    print(
        f"Documentation validation passed ({len(markdown_files)} Markdown files; "
        f"links, environment names, commands, and tracked artifacts checked)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
