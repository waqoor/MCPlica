#!/usr/bin/env python3
"""Generate or verify the deterministic Git-tracked source snapshot manifest."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.sha256"
EXCLUDED = frozenset({"MANIFEST.sha256"})


def tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    paths = result.stdout.decode("utf-8").split("\0")
    return sorted(
        path.replace("\\", "/")
        for path in paths
        if path and path not in EXCLUDED and (ROOT / path).is_file()
    )


def render(paths: list[str]) -> str:
    lines = [
        f"{hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}  ./{path}" for path in paths
    ]
    return "\n".join(lines) + "\n"


def verify(expected: str) -> list[str]:
    if not MANIFEST.is_file():
        return ["MANIFEST.sha256 is missing"]
    actual = MANIFEST.read_text(encoding="utf-8")
    if actual == expected:
        return []
    actual_lines = actual.splitlines()
    duplicate_paths: set[str] = set()
    seen: set[str] = set()
    for line in actual_lines:
        parts = line.split("  ./", maxsplit=1)
        if len(parts) != 2:
            continue
        if parts[1] in seen:
            duplicate_paths.add(parts[1])
        seen.add(parts[1])
    errors = ["MANIFEST.sha256 differs from the current Git-tracked source snapshot"]
    if duplicate_paths:
        errors.append("duplicate entries: " + ", ".join(sorted(duplicate_paths)))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    action.add_argument("--stdout", action="store_true")
    args = parser.parse_args()
    expected = render(tracked_paths())
    if args.write:
        MANIFEST.write_text(expected, encoding="utf-8", newline="\n")
        return 0
    if args.stdout:
        sys.stdout.write(expected)
        return 0
    errors = verify(expected)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
