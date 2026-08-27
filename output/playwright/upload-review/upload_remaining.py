from __future__ import annotations

import json
import re
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[3]
PROJECT_ID = "845d3c75-ca77-4026-ab2b-dc04260b741b"
BASE_URL = "http://localhost:8000/api/v1"


def development_credential(name: str) -> str:
    source = (ROOT / "backend/app/cli/ensure_development_admin.py").read_text(
        encoding="utf-8"
    )
    match = re.search(rf'^{name} = "([^"]+)"$', source, flags=re.MULTILINE)
    if match is None:
        raise RuntimeError(f"Unable to find {name}")
    return match.group(1)


items = [
    ("Markdown document upload", "sample.md", "text/markdown"),
    ("Text document upload", "sample.txt", "text/plain"),
    ("CSV document upload", "sample.csv", "text/csv"),
    (
        "XLSX document upload",
        "sample.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    (
        "DOCX document upload",
        "sample.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    ("PDF document upload", "sample.pdf", "application/pdf"),
]


with httpx.Client(base_url=BASE_URL, timeout=60.0, trust_env=False) as client:
    login = client.post(
        "/auth/login",
        json={
            "email": development_credential("DEFAULT_DEVELOPMENT_ADMIN_EMAIL"),
            "password": development_credential("DEFAULT_DEVELOPMENT_ADMIN_PASSWORD"),
        },
    )
    login.raise_for_status()
    csrf = client.cookies.get("mcplica_csrf")
    if not csrf:
        raise RuntimeError("Login did not set the CSRF cookie")
    headers = {"X-CSRF-Token": csrf}

    current = client.get(f"/projects/{PROJECT_ID}/sources")
    current.raise_for_status()
    sources_by_name = {source["name"]: source for source in current.json()}

    for source_name, filename, media_type in items:
        if source_name in sources_by_name:
            continue
        created = client.post(
            f"/projects/{PROJECT_ID}/sources",
            headers=headers,
            json={
                "kind": "documentation",
                "name": source_name,
                "origin_type": "upload",
                "is_primary": False,
            },
        )
        created.raise_for_status()
        source_id = created.json()["id"]
        content = (Path(__file__).parent / filename).read_bytes()
        uploaded = client.post(
            f"/projects/{PROJECT_ID}/sources/{source_id}/versions",
            headers=headers,
            files={"file": (filename, content, media_type)},
        )
        if uploaded.status_code != 201:
            raise RuntimeError(
                f"{source_name} upload returned {uploaded.status_code}: {uploaded.text}"
            )

    refreshed = client.get(f"/projects/{PROJECT_ID}/sources")
    refreshed.raise_for_status()
    requested = {}
    requested_names = {"JSON document upload", *(item[0] for item in items)}
    for source in refreshed.json():
        if source["name"] not in requested_names:
            continue
        versions = client.get(
            f"/projects/{PROJECT_ID}/sources/{source['id']}/versions"
        )
        versions.raise_for_status()
        latest = max(versions.json(), key=lambda version: version["created_at"])
        requested[source["name"]] = {
            "detected_format": latest["detected_format"],
            "size_bytes": latest["byte_size"],
        }
    print(json.dumps(requested, indent=2, sort_keys=True))
