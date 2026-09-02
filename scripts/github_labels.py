#!/usr/bin/env python3
"""Validate or apply MCPlica's repository-managed GitHub label catalog."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / ".github/labels.json"


def load_catalog() -> list[dict[str, str]]:
    loaded = json.loads(CATALOG.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise ValueError(".github/labels.json must contain an array")
    labels: list[dict[str, str]] = []
    names: set[str] = set()
    for index, raw in enumerate(cast(list[object], loaded)):
        if not isinstance(raw, dict):
            raise ValueError(f"label {index} must be an object")
        item = cast(dict[str, object], raw)
        if set(item) != {"name", "color", "description"}:
            raise ValueError(f"label {index} has unexpected or missing fields")
        label = {key: str(value) for key, value in item.items()}
        if not label["name"] or label["name"] in names:
            raise ValueError(f"label name is empty or duplicated: {label['name']!r}")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", label["color"]):
            raise ValueError(f"label {label['name']!r} has an invalid color")
        if not label["description"] or len(label["description"]) > 100:
            raise ValueError(f"label {label['name']!r} has an invalid description")
        names.add(label["name"])
        labels.append(label)
    return labels


def template_labels() -> set[str]:
    labels: set[str] = set()
    for path in sorted((ROOT / ".github/ISSUE_TEMPLATE").glob("*.yml")):
        match = re.search(r"(?m)^labels:\s*\[([^]]*)\]\s*$", path.read_text(encoding="utf-8"))
        if not match:
            continue
        labels.update(value.strip().strip("'\"") for value in match.group(1).split(","))
    return labels


def validate(labels: list[dict[str, str]]) -> None:
    known = {label["name"] for label in labels}
    missing = template_labels() - known
    if missing:
        raise ValueError("issue templates use uncatalogued labels: " + ", ".join(sorted(missing)))


def request(method: str, url: str, token: str, payload: dict[str, str] | None = None) -> object:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "mcplica-label-sync",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def apply(labels: list[dict[str, str]]) -> None:
    token = os.getenv("GH_TOKEN")
    repository = os.getenv("GITHUB_REPOSITORY")
    if not token or not repository or not re.fullmatch(r"[^/]+/[^/]+", repository):
        raise ValueError("--apply requires GH_TOKEN and an owner/repository GITHUB_REPOSITORY")
    base = f"https://api.github.com/repos/{repository}/labels"
    existing: list[dict[str, object]] = []
    for page in range(1, 101):
        batch = cast(
            list[dict[str, object]],
            request("GET", f"{base}?per_page=100&page={page}", token),
        )
        existing.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise ValueError("repository label pagination exceeded 10,000 labels")
    existing_names = {str(label["name"]) for label in existing}
    for label in labels:
        if label["name"] in existing_names:
            encoded = urllib.parse.quote(label["name"], safe="")
            request(
                "PATCH",
                f"{base}/{encoded}",
                token,
                {"color": label["color"], "description": label["description"]},
            )
        else:
            request("POST", base, token, label)
    print(f"Applied {len(labels)} managed labels without deleting unmanaged labels.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.check == args.apply:
        parser.error("choose exactly one of --check or --apply")
    try:
        labels = load_catalog()
        validate(labels)
        if args.apply:
            apply(labels)
        else:
            print(f"GitHub label catalog is valid ({len(labels)} labels).")
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        print(f"GitHub label validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
