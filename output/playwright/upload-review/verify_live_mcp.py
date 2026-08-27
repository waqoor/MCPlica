from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


SCRIPT_PATH = Path(__file__).resolve()
ROOT = SCRIPT_PATH.parents[3] if len(SCRIPT_PATH.parents) > 3 else Path("/workspace")
PROJECT_ID = "845d3c75-ca77-4026-ab2b-dc04260b741b"
BUILD_ID = "7f8f3088-eabd-4f32-b524-dad95a2ad5aa"
BASE_URL = "http://host.docker.internal:8000/api/v1"
MCP_URL = "http://host.docker.internal/mcp"
MCP_HOSTNAME = "final-acceptance.mcp.localhost"
REQUESTED_SOURCE_NAMES = {
    "JSON document upload",
    "Markdown document upload",
    "Text document upload",
    "CSV document upload",
    "XLSX document upload",
    "DOCX document upload",
    "PDF document upload",
}


def development_credential(name: str) -> str:
    source_path = ROOT / "backend/app/cli/ensure_development_admin.py"
    if not source_path.exists():
        source_path = Path("/tmp/ensure_development_admin.py")
    source = source_path.read_text(encoding="utf-8")
    match = re.search(rf'^{name} = "([^"]+)"$', source, flags=re.MULTILINE)
    if match is None:
        raise RuntimeError(f"Unable to find {name}")
    return match.group(1)


async def checked_json(response: httpx.Response, expected: int = 200) -> object:
    if response.status_code != expected:
        raise RuntimeError(
            f"{response.request.method} {response.request.url.path} returned "
            f"{response.status_code}: {response.text}"
        )
    return response.json()


async def deployment_ids(control: httpx.AsyncClient) -> set[str]:
    deployments = await checked_json(
        await control.get(f"/projects/{PROJECT_ID}/deployments")
    )
    if not isinstance(deployments, list):
        raise RuntimeError("Deployments response was malformed")
    return {
        str(deployment["id"])
        for deployment in deployments
        if isinstance(deployment, dict) and isinstance(deployment.get("id"), str)
    }


async def wait_for_new_running_deployment(
    control: httpx.AsyncClient, previous_ids: set[str]
) -> dict[str, object]:
    deadline = asyncio.get_running_loop().time() + 120
    while asyncio.get_running_loop().time() < deadline:
        deployments = await checked_json(
            await control.get(f"/projects/{PROJECT_ID}/deployments")
        )
        if not isinstance(deployments, list):
            raise RuntimeError("Deployments response was malformed")
        candidates = [
            deployment
            for deployment in deployments
            if isinstance(deployment, dict)
            and isinstance(deployment.get("id"), str)
            and deployment["id"] not in previous_ids
        ]
        if candidates:
            latest = max(candidates, key=lambda item: item["created_at"])
            if latest.get("status") == "running" and latest.get("health_status") == "healthy":
                return latest
            if latest.get("status") in {"failed", "unhealthy", "stopped"}:
                raise RuntimeError(
                    "Secret-bundle rollout failed: "
                    f"{latest.get('error_code')}: {latest.get('error_summary')}"
                )
        await asyncio.sleep(1)
    raise RuntimeError("Timed out waiting for the secret-bundle runtime rollout")


async def main() -> None:
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=httpx.Timeout(60),
        trust_env=False,
    ) as control:
        await checked_json(
            await control.post(
                "/auth/login",
                json={
                    "email": development_credential(
                        "DEFAULT_DEVELOPMENT_ADMIN_EMAIL"
                    ),
                    "password": development_credential(
                        "DEFAULT_DEVELOPMENT_ADMIN_PASSWORD"
                    ),
                },
            )
        )
        csrf = control.cookies.get("mcplica_csrf")
        if not csrf:
            raise RuntimeError("Login did not set the CSRF cookie")
        mutation_headers = {"X-CSRF-Token": csrf}

        build = await checked_json(await control.get(f"/builds/{BUILD_ID}"))
        if not isinstance(build, dict) or build.get("status") != "READY":
            raise RuntimeError("The uploaded-source build is not READY")

        validation = await checked_json(
            await control.get(f"/builds/{BUILD_ID}/validation")
        )
        if not isinstance(validation, dict) or validation.get("overall_status") != "pass":
            raise RuntimeError("Build validation did not pass")

        operations = await checked_json(
            await control.get(f"/builds/{BUILD_ID}/operations")
        )
        if not isinstance(operations, list):
            raise RuntimeError("Build operations response was malformed")
        get_widget = next(
            (
                operation.get("tool_name")
                for operation in operations
                if isinstance(operation, dict)
                and operation.get("source_operation_id") == "getWidget"
            ),
            None,
        )
        if not isinstance(get_widget, str):
            raise RuntimeError("getWidget was not compiled into an MCP tool")

        manifest = await checked_json(await control.get(f"/builds/{BUILD_ID}/manifest"))
        if not isinstance(manifest, dict):
            raise RuntimeError("Build manifest was malformed")
        manifest_tools = manifest.get("tools")
        manifest_resources = manifest.get("resources")
        if not isinstance(manifest_tools, list) or not isinstance(manifest_resources, list):
            raise RuntimeError("Build manifest lacked tools or documentation resources")

        ai_runs = await checked_json(await control.get(f"/builds/{BUILD_ID}/ai-runs"))
        if not isinstance(ai_runs, list) or not ai_runs:
            raise RuntimeError("Build did not record AI runs")
        if any(
            not isinstance(run, dict) or run.get("status") != "succeeded"
            for run in ai_runs
        ):
            raise RuntimeError("At least one build-time AI run did not succeed")
        retrieved_ids = {
            chunk_id
            for run in ai_runs
            if isinstance(run, dict)
            for chunk_id in run.get("retrieved_chunk_ids", [])
            if isinstance(chunk_id, str)
        }
        if not retrieved_ids:
            raise RuntimeError("AI runs did not retrieve uploaded documentation chunks")

        sources = await checked_json(
            await control.get(f"/projects/{PROJECT_ID}/sources")
        )
        if not isinstance(sources, list):
            raise RuntimeError("Sources response was malformed")
        source_metadata: dict[str, dict[str, object]] = {}
        for source in sources:
            if not isinstance(source, dict) or source.get("name") not in REQUESTED_SOURCE_NAMES:
                continue
            versions = await checked_json(
                await control.get(
                    f"/projects/{PROJECT_ID}/sources/{source['id']}/versions"
                )
            )
            if not isinstance(versions, list) or not versions:
                raise RuntimeError(f"{source['name']} has no immutable version")
            latest = max(versions, key=lambda version: version["created_at"])
            metadata = await checked_json(
                await control.get(f"/source-versions/{latest['id']}/metadata")
            )
            if (
                not isinstance(metadata, dict)
                or metadata.get("parse_status") != "valid"
                or not isinstance(metadata.get("indexed_chunk_count"), int)
                or metadata["indexed_chunk_count"] < 1
            ):
                raise RuntimeError(f"{source['name']} was not parsed and indexed")
            source_metadata[str(source["name"])] = {
                "format": metadata["detected_format"],
                "indexed_chunks": metadata["indexed_chunk_count"],
            }
        if set(source_metadata) != REQUESTED_SOURCE_NAMES:
            raise RuntimeError("Not all requested uploaded formats reached the index")

        deployments_before_token = await deployment_ids(control)
        issued = await checked_json(
            await control.post(
                f"/projects/{PROJECT_ID}/mcp-access/tokens",
                headers=mutation_headers,
                json={"name": "Transient upload review", "expires_at": None},
            ),
            expected=201,
        )
        if not isinstance(issued, dict) or not isinstance(issued.get("plaintext"), str):
            raise RuntimeError("Transient MCP access token was not issued")
        token = issued["plaintext"]
        token_record = issued.get("token")
        if not isinstance(token_record, dict) or not isinstance(token_record.get("id"), str):
            raise RuntimeError("Transient MCP token record was malformed")
        token_id = token_record["id"]
        token_rollout = await wait_for_new_running_deployment(
            control, deployments_before_token
        )

        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Host": MCP_HOSTNAME,
            }
            async with httpx2.AsyncClient(
                headers=headers,
                timeout=httpx2.Timeout(30),
                follow_redirects=False,
                trust_env=False,
            ) as mcp_http:
                transport = streamable_http_client(
                    MCP_URL,
                    http_client=mcp_http,
                    terminate_on_close=True,
                )
                async with Client(transport, read_timeout_seconds=30, cache=None) as mcp:
                    tools = await mcp.list_tools(cache_mode="bypass")
                    resources = await mcp.list_resources(cache_mode="bypass")
                    if not resources.resources:
                        raise RuntimeError("Deployed MCP service exposed no documentation resources")
                    resource = await mcp.read_resource(resources.resources[0].uri)
                    if not resource.contents:
                        raise RuntimeError("Deployed MCP documentation resource was empty")
                    result = await mcp.call_tool(
                        get_widget,
                        {"widget_id": "upload-review", "verbose": True},
                    )
                    if result.is_error or not isinstance(result.structured_content, dict):
                        raise RuntimeError("Deployed getWidget MCP call failed")
                    call_result = result.structured_content
                    if (
                        call_result.get("method") != "GET"
                        or call_result.get("path") != "/api/widgets/upload-review"
                    ):
                        raise RuntimeError("MCP runtime changed the compiled upstream mapping")
                    live_tool_names = [tool.name for tool in tools.tools]
                    live_resource_count = len(resources.resources)
        finally:
            deployments_before_revoke = await deployment_ids(control)
            revoked = await control.delete(
                f"/projects/{PROJECT_ID}/mcp-access/tokens/{token_id}",
                headers=mutation_headers,
            )
            if revoked.status_code != 200:
                raise RuntimeError("Transient MCP token could not be revoked")
            cleanup_rollout = await wait_for_new_running_deployment(
                control, deployments_before_revoke
            )

        print(
            json.dumps(
                {
                    "ai_run_count": len(ai_runs),
                    "build_id": BUILD_ID,
                    "build_status": build["status"],
                    "indexed_sources": source_metadata,
                    "manifest_resource_count": len(manifest_resources),
                    "manifest_tool_count": len(manifest_tools),
                    "mcp_call": {
                        "method": call_result["method"],
                        "path": call_result["path"],
                    },
                    "mcp_resource_count": live_resource_count,
                    "mcp_tool_names": live_tool_names,
                    "retrieved_chunk_count": len(retrieved_ids),
                    "runtime_rollouts": {
                        "cleanup": cleanup_rollout["id"],
                        "token_activation": token_rollout["id"],
                    },
                    "validation": validation["overall_status"],
                },
                indent=2,
                sort_keys=True,
            )
        )


asyncio.run(main())
