#!/usr/bin/env python3
"""Synchronize and verify release-version consumers against the root VERSION file."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9A-Za-z-][0-9A-Za-z-]*))*))?$"
)
PROJECT_FILES = (
    Path("pyproject.toml"),
    Path("backend/pyproject.toml"),
    Path("mcp_runtime/pyproject.toml"),
    Path("packages/contracts/pyproject.toml"),
)
WORKSPACE_PACKAGES = {
    "mcplica-workspace",
    "mcplica-backend",
    "mcplica-runtime",
    "mcplica-contracts",
}


def authoritative_version() -> str:
    if not VERSION_FILE.is_file():
        raise ValueError("VERSION is missing")
    value = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not SEMVER.fullmatch(value):
        raise ValueError(
            "VERSION must be SemVer without a leading v or build metadata "
            "(for example 1.2.3 or 1.2.3-rc.1)"
        )
    return value


def _replace_once(path: Path, pattern: str, replacement: str) -> None:
    target = ROOT / path
    value = target.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, value, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"could not locate exactly one version field in {path.as_posix()}")
    target.write_text(updated, encoding="utf-8", newline="\n")


def synchronize(version: str) -> None:
    for path in PROJECT_FILES:
        _replace_once(path, r'^version = "[^"]+"$', f'version = "{version}"')

    package_path = ROOT / "frontend/package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = version
    package_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8", newline="\n")

    _replace_once(
        Path("packages/contracts/src/mcp_contracts/version.py"),
        r'^VERSION = "[^"]+"$',
        f'VERSION = "{version}"',
    )
    _replace_once(
        Path("tests/fixtures/manifests/petstore.json"),
        r'^    "compiler_version": "[^"]+"$',
        f'    "compiler_version": "{version}"',
    )
    _replace_once(Path(".env.example"), r"^MCPLICA_VERSION=.*$", f"MCPLICA_VERSION={version}")

    lock_path = ROOT / "uv.lock"
    lock = lock_path.read_text(encoding="utf-8")
    for package_name in sorted(WORKSPACE_PACKAGES):
        pattern = (
            r'(\[\[package\]\]\r?\nname = "'
            + re.escape(package_name)
            + r'"\r?\nversion = ")[^"]+("\r?\n)'
        )
        lock, count = re.subn(pattern, rf"\g<1>{version}\g<2>", lock, count=1)
        if count != 1:
            raise ValueError(f"could not locate {package_name} in uv.lock")
    lock_path.write_text(lock, encoding="utf-8", newline="\n")

    openapi_path = ROOT / "openapi.json"
    openapi = json.loads(openapi_path.read_text(encoding="utf-8"))
    openapi["info"]["version"] = version
    openapi_path.write_text(
        json.dumps(
            openapi,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
            separators=(",", ": "),
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _value_after_equals(path: Path, key: str) -> str | None:
    prefix = key + "="
    for line in (ROOT / path).read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip().strip("'\"")
    return None


def verify(version: str, *, tag: str | None = None) -> list[str]:
    errors: list[str] = []
    for path in PROJECT_FILES:
        value = tomllib.loads((ROOT / path).read_text(encoding="utf-8"))["project"]["version"]
        if value != version:
            errors.append(f"{path.as_posix()} has {value!r}, expected {version!r}")

    frontend = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    if frontend.get("version") != version:
        errors.append("frontend/package.json does not match VERSION")

    version_module = (ROOT / "packages/contracts/src/mcp_contracts/version.py").read_text(
        encoding="utf-8"
    )
    if f'VERSION = "{version}"' not in version_module:
        errors.append("shared-contract product version does not match VERSION")

    fixture = json.loads(
        (ROOT / "tests/fixtures/manifests/petstore.json").read_text(encoding="utf-8")
    )
    if fixture.get("build", {}).get("compiler_version") != version:
        errors.append("the runtime acceptance manifest compiler version does not match VERSION")

    if _value_after_equals(Path(".env.example"), "MCPLICA_VERSION") != version:
        errors.append(".env.example MCPLICA_VERSION does not match VERSION")

    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    locked_versions = {
        item["name"]: item["version"]
        for item in lock["package"]
        if item["name"] in WORKSPACE_PACKAGES
    }
    missing_packages = WORKSPACE_PACKAGES - locked_versions.keys()
    if missing_packages:
        errors.append(
            "uv.lock is missing workspace packages: " + ", ".join(sorted(missing_packages))
        )
    for name, value in sorted(locked_versions.items()):
        if value != version:
            errors.append(f"uv.lock {name} has {value!r}, expected {version!r}")

    openapi = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
    if openapi.get("info", {}).get("version") != version:
        errors.append("openapi.json info.version does not match VERSION")

    changelog = ROOT / "CHANGELOG.md"
    if not changelog.is_file() or f"## [{version}] - " not in changelog.read_text(encoding="utf-8"):
        errors.append(f"CHANGELOG.md is missing a dated [{version}] release section")

    notes = ROOT / "docs" / "releases" / f"v{version}.md"
    if not notes.is_file():
        errors.append(f"release notes are missing: {notes.relative_to(ROOT).as_posix()}")

    if tag is not None and tag != f"v{version}":
        errors.append(f"release tag {tag!r} must exactly match VERSION as v{version}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="verify every release-version copy")
    action.add_argument("--sync", action="store_true", help="rewrite generated version copies")
    action.add_argument("--print", action="store_true", dest="print_version")
    parser.add_argument("--tag", help="also require this tag to equal v<VERSION>")
    args = parser.parse_args()
    try:
        version = authoritative_version()
        if args.sync:
            synchronize(version)
        elif args.print_version:
            print(version)
            return 0
        errors = verify(version, tag=args.tag)
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
    ) as exc:
        print(f"release version validation failed: {exc}", file=sys.stderr)
        return 1
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    print(f"MCPlica release version {version} is synchronized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
