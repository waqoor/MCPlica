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


def _is_canonical_numeric_identifier(value: str) -> bool:
    return (
        bool(value)
        and all("0" <= char <= "9" for char in value)
        and (value == "0" or not value.startswith("0"))
    )


def _parse_semver(value: str) -> tuple[int, int, int, str | None]:
    """Parse the supported SemVer subset without backtracking regular expressions."""
    if not value or "+" in value:
        raise ValueError("build metadata and empty versions are not supported")

    core, separator, prerelease = value.partition("-")
    core_identifiers = core.split(".")
    if len(core_identifiers) != 3 or not all(
        _is_canonical_numeric_identifier(identifier) for identifier in core_identifiers
    ):
        raise ValueError("the core version must contain three canonical numeric identifiers")

    if separator:
        prerelease_identifiers = prerelease.split(".")
        if any(
            not identifier
            or any(
                not ("0" <= char <= "9" or "A" <= char <= "Z" or "a" <= char <= "z" or char == "-")
                for char in identifier
            )
            or (
                all("0" <= char <= "9" for char in identifier)
                and not _is_canonical_numeric_identifier(identifier)
            )
            for identifier in prerelease_identifiers
        ):
            raise ValueError("the prerelease contains an invalid identifier")
    else:
        prerelease = None

    major, minor, patch = (int(identifier) for identifier in core_identifiers)
    return major, minor, patch, prerelease


def authoritative_version() -> str:
    if not VERSION_FILE.is_file():
        raise ValueError("VERSION is missing")
    value = VERSION_FILE.read_text(encoding="utf-8").strip()
    try:
        _parse_semver(value)
    except ValueError as exc:
        raise ValueError(
            "VERSION must be SemVer without a leading v or build metadata "
            "(for example 1.2.3 or 1.2.3-rc.1)"
        ) from exc
    return value


def runtime_compatibility(version: str) -> str:
    try:
        major, _, _, prerelease = _parse_semver(version)
    except ValueError as exc:
        raise ValueError("cannot derive runtime compatibility from an invalid version") from exc
    lower_bound = version if prerelease is not None else f"{major}.0"
    return f">={lower_bound},<{major + 1}.0"


def _replace_once(path: Path, pattern: str, replacement: str) -> None:
    target = ROOT / path
    value = target.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, value, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"could not locate exactly one version field in {path.as_posix()}")
    target.write_text(updated, encoding="utf-8", newline="\n")


def synchronize(version: str) -> None:
    compatibility = runtime_compatibility(version)
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
        Path("packages/contracts/src/mcp_contracts/version.py"),
        r'^RUNTIME_COMPATIBILITY = "[^"]+"$',
        f'RUNTIME_COMPATIBILITY = "{compatibility}"',
    )
    _replace_once(
        Path("tests/fixtures/manifests/petstore.json"),
        r'^  "runtime_compatibility": "[^"]+",$',
        f'  "runtime_compatibility": "{compatibility}",',
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
    compatibility = runtime_compatibility(version)
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
    if f'RUNTIME_COMPATIBILITY = "{compatibility}"' not in version_module:
        errors.append("shared-contract runtime compatibility does not match VERSION")

    manifest_fixture_root = ROOT / "tests/fixtures/manifests"
    for fixture_path in sorted(manifest_fixture_root.glob("*.json")):
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        relative_path = fixture_path.relative_to(ROOT).as_posix()
        if fixture.get("build", {}).get("compiler_version") != version:
            errors.append(f"{relative_path} compiler version does not match VERSION")
        if fixture.get("runtime_compatibility") != compatibility:
            errors.append(f"{relative_path} runtime compatibility does not match VERSION")

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
    openapi_compatibility = (
        openapi.get("components", {})
        .get("schemas", {})
        .get("MCPManifest", {})
        .get("properties", {})
        .get("runtime_compatibility", {})
        .get("default")
    )
    if openapi_compatibility != compatibility:
        errors.append("openapi.json runtime compatibility does not match VERSION")

    manifest_schema = json.loads(
        (ROOT / "packages/contracts/schemas/mcp-manifest-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    schema_compatibility = (
        manifest_schema.get("properties", {}).get("runtime_compatibility", {}).get("default")
    )
    if schema_compatibility != compatibility:
        errors.append("manifest JSON Schema runtime compatibility does not match VERSION")

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
