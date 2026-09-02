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


def tracked_entries() -> list[tuple[str, str]]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--stage"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    entries: list[tuple[str, str]] = []
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        metadata, separator, encoded_path = record.partition(b"\t")
        if not separator:
            raise RuntimeError("Git returned an invalid index record")
        _mode, object_id, stage = metadata.decode("ascii").split()
        if stage != "0":
            raise RuntimeError("Cannot create a source manifest from an unmerged Git index")
        path = encoded_path.decode("utf-8").replace("\\", "/")
        if path not in EXCLUDED:
            entries.append((path, object_id))
    return sorted(entries)


def read_index_blobs(object_ids: list[str]) -> list[bytes]:
    if not object_ids:
        return []
    result = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=ROOT,
        check=True,
        input=("\n".join(object_ids) + "\n").encode("ascii"),
        capture_output=True,
    )
    payload = result.stdout
    offset = 0
    blobs: list[bytes] = []
    for expected_id in object_ids:
        header_end = payload.find(b"\n", offset)
        if header_end < 0:
            raise RuntimeError("Git returned a truncated batch header")
        header = payload[offset:header_end].decode("ascii").split()
        if len(header) != 3:
            raise RuntimeError("Git returned an invalid batch header")
        object_id, object_type, size_text = header
        if object_id != expected_id or object_type != "blob":
            raise RuntimeError(f"Expected Git blob {expected_id}, received {' '.join(header[:2])}")
        size = int(size_text)
        content_start = header_end + 1
        content_end = content_start + size
        if content_end >= len(payload) or payload[content_end : content_end + 1] != b"\n":
            raise RuntimeError(f"Git returned truncated content for blob {expected_id}")
        blobs.append(payload[content_start:content_end])
        offset = content_end + 1
    if offset != len(payload):
        raise RuntimeError("Git returned unexpected trailing batch content")
    return blobs


def render(entries: list[tuple[str, str]]) -> str:
    blobs = read_index_blobs([object_id for _path, object_id in entries])
    lines = [
        f"{hashlib.sha256(blob).hexdigest()}  ./{path}"
        for (path, _object_id), blob in zip(entries, blobs, strict=True)
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
    expected = render(tracked_entries())
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
