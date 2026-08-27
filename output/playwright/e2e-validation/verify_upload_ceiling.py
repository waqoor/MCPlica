from __future__ import annotations

import json
import os
import re
from pathlib import Path

import httpx


BASE_URL = os.getenv(
    "E2E_API_BASE", "http://host.docker.internal:8000/api/v1"
)
PROJECT_ID = "845d3c75-ca77-4026-ab2b-dc04260b741b"
EXPECTED_LIMIT = 100_000_000
OVERSIZED_FILE = Path("/tmp/one-byte-too-large.txt")


def development_credential(name: str) -> str:
    source = Path("/workspace/backend/app/cli/ensure_development_admin.py").read_text(
        encoding="utf-8"
    )
    match = re.search(rf'^{name} = "([^"]+)"$', source, flags=re.MULTILINE)
    if match is None:
        raise RuntimeError(f"Unable to find {name}")
    return match.group(1)


with httpx.Client(base_url=BASE_URL, timeout=180.0, trust_env=False) as client:
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

    settings = client.get("/settings")
    settings.raise_for_status()
    configured_limit = settings.json()["max_upload_bytes"]
    if configured_limit != EXPECTED_LIMIT:
        raise RuntimeError(
            f"Expected a {EXPECTED_LIMIT}-byte upload limit, got {configured_limit}"
        )

    sources = client.get(f"/projects/{PROJECT_ID}/sources")
    sources.raise_for_status()
    source = next(
        item for item in sources.json() if item["name"] == "Text document upload"
    )
    versions_url = f"/projects/{PROJECT_ID}/sources/{source['id']}/versions"
    before_response = client.get(versions_url)
    before_response.raise_for_status()
    before_ids = {item["id"] for item in before_response.json()}

    if OVERSIZED_FILE.stat().st_size != EXPECTED_LIMIT + 1:
        raise RuntimeError("Oversized boundary fixture has the wrong byte size")
    with OVERSIZED_FILE.open("rb") as oversized:
        response = client.post(
            versions_url,
            headers={"X-CSRF-Token": csrf},
            files={
                "file": (
                    "one-byte-too-large.txt",
                    oversized,
                    "text/plain",
                )
            },
        )
    if response.status_code != 413:
        raise RuntimeError(
            f"Oversized upload returned {response.status_code}: {response.text}"
        )

    after_response = client.get(versions_url)
    after_response.raise_for_status()
    after_ids = {item["id"] for item in after_response.json()}
    if after_ids != before_ids:
        raise RuntimeError("Rejected upload unexpectedly created a source version")

    print(
        json.dumps(
            {
                "configured_limit_bytes": configured_limit,
                "rejected_size_bytes": EXPECTED_LIMIT + 1,
                "response": response.json(),
                "source_versions_unchanged": True,
                "status_code": response.status_code,
            },
            indent=2,
            sort_keys=True,
        )
    )
