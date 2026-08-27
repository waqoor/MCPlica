"""Run MCPlica's complete clean-install acceptance workflow against Docker Compose.

This is an explicit release harness, not part of the ordinary unit-test suite. It uses
real control-plane services, workers, Milvus, Docker deployment, Traefik, the generic
runtime, and the official MCP client. Only OpenRouter and the source product API are
deterministic local HTTP fixtures.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import secrets
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import cast

import httpx
import httpx2
import uvicorn
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mock_openrouter.app import app as openrouter_app
from mock_upstream.app import app as upstream_app
from starlette.applications import Starlette

from app.clients.mcp import MCPValidationClient

_TERMINAL_BUILD_STATUSES = {"READY", "FAILED", "CANCELLED"}
_TERMINAL_DEPLOYMENT_STATUSES = {"running", "unhealthy", "stopped", "failed"}


def _assert_superseded_before_running(
    superseded: dict[str, object],
    replacement: dict[str, object],
) -> None:
    if superseded.get("status") != "stopped":
        raise RuntimeError("RUNNING replacement did not retire the superseded runtime")
    stopped_at = superseded.get("stopped_at")
    started_at = replacement.get("started_at")
    if not isinstance(stopped_at, str) or not isinstance(started_at, str):
        raise RuntimeError("deployment lifecycle timestamps are missing")
    if datetime.fromisoformat(stopped_at) > datetime.fromisoformat(started_at):
        raise RuntimeError("replacement became RUNNING before the superseded runtime stopped")


@dataclass(slots=True)
class FixtureServer:
    app: Starlette
    port: int
    server: uvicorn.Server | None = None
    task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self.server = uvicorn.Server(config)
        self.task = asyncio.create_task(self.server.serve())
        deadline = time.monotonic() + 20
        async with httpx.AsyncClient(trust_env=False) as client:
            while time.monotonic() < deadline:
                if self.task.done():
                    await self.task
                    raise RuntimeError(f"fixture server on port {self.port} stopped during startup")
                try:
                    response = await client.get(f"http://127.0.0.1:{self.port}/healthz")
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.2)
        raise RuntimeError(f"fixture server on port {self.port} did not become healthy")

    async def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
        if self.task is not None:
            await asyncio.wait_for(self.task, timeout=15)
        self.server = None
        self.task = None


class ControlPlaneClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            follow_redirects=False,
            timeout=httpx.Timeout(60),
            trust_env=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def login(self, *, email: str, password: str) -> dict[str, object]:
        return await self.json(
            "POST",
            "/auth/login",
            expected=frozenset({200}),
            json_body={"email": email, "password": password},
            csrf=False,
        )

    async def json(
        self,
        method: str,
        path: str,
        *,
        expected: frozenset[int] | None = None,
        csrf: bool = True,
        json_body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        headers: dict[str, str] = {}
        if csrf and method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            token = self._client.cookies.get("mcplica_csrf")
            if not token:
                raise RuntimeError("control-plane session has no CSRF token")
            headers["X-CSRF-Token"] = token
        response = await self._client.request(method, path, headers=headers, json=json_body)
        if response.status_code not in (expected or frozenset({200})):
            raise RuntimeError(f"{method.upper()} {path} returned HTTP {response.status_code}")
        value = cast(object, response.json())
        if not isinstance(value, dict):
            raise RuntimeError(f"{method.upper()} {path} returned a non-object JSON response")
        return cast(dict[str, object], value)

    async def json_list(self, path: str) -> list[dict[str, object]]:
        response = await self._client.get(path)
        if response.status_code != 200:
            raise RuntimeError(f"GET {path} returned HTTP {response.status_code}")
        value = cast(object, response.json())
        if not isinstance(value, list) or any(
            not isinstance(item, dict) for item in cast(list[object], value)
        ):
            raise RuntimeError(f"GET {path} returned a malformed list")
        return cast(list[dict[str, object]], value)

    async def upload(
        self,
        path: str,
        *,
        filename: str,
        media_type: str,
        content: bytes,
    ) -> dict[str, object]:
        token = self._client.cookies.get("mcplica_csrf")
        if not token:
            raise RuntimeError("control-plane session has no CSRF token")
        response = await self._client.post(
            path,
            headers={"X-CSRF-Token": token},
            files={"file": (filename, content, media_type)},
        )
        if response.status_code != 201:
            raise RuntimeError(f"POST {path} returned HTTP {response.status_code}")
        value = cast(object, response.json())
        if not isinstance(value, dict):
            raise RuntimeError(f"POST {path} returned malformed JSON")
        return cast(dict[str, object], value)

    async def bytes(self, path: str) -> bytes:
        response = await self._client.get(path)
        if response.status_code != 200:
            raise RuntimeError(f"GET {path} returned HTTP {response.status_code}")
        return response.content


def _openapi(*, updated: bool) -> bytes:
    security: list[dict[str, list[str]]] = [{"bearerAuth": []}]
    paths: dict[str, object] = {
        "/widgets/{widget_id}": {
            "get": {
                "operationId": "getWidget",
                "summary": "Get one widget",
                "description": "Read a widget by its stable identifier.",
                "security": security,
                "parameters": [
                    {
                        "name": "widget_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "verbose",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "boolean"},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Widget response",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object", "additionalProperties": True}
                            }
                        },
                    }
                },
            },
            "patch": {
                "operationId": "updateWidget",
                "summary": "Update one widget",
                "security": security,
                "parameters": [
                    {
                        "name": "widget_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                                "required": ["name"],
                                "additionalProperties": False,
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "Updated"}},
            },
            "delete": {
                "operationId": "deleteWidget",
                "summary": "Delete one widget",
                "security": security,
                "parameters": [
                    {
                        "name": "widget_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {"200": {"description": "Deleted"}},
            },
        },
        "/widgets": {
            "post": {
                "operationId": "createWidget",
                "summary": "Create a widget",
                "security": security,
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                                "required": ["name"],
                                "additionalProperties": False,
                            }
                        }
                    },
                },
                "responses": {"201": {"description": "Created"}},
            }
        },
    }
    if updated:
        paths["/widgets/search"] = {
            "get": {
                "operationId": "searchWidgets",
                "summary": "Search widgets",
                "description": "Search the current widget catalog.",
                "security": security,
                "responses": {"200": {"description": "Search results"}},
            }
        }
    document = {
        "openapi": "3.1.0",
        "info": {
            "title": "MCPlica final acceptance API",
            "version": "2.0.0" if updated else "1.0.0",
        },
        "servers": [{"url": "http://host.docker.internal:9009/api"}],
        "components": {"securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}}},
        "paths": paths,
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


async def _poll_build(client: ControlPlaneClient, build_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 300
    previous: object = None
    while time.monotonic() < deadline:
        build = await client.json("GET", f"/builds/{build_id}", csrf=False)
        status = build.get("status")
        if status != previous:
            print(f"build {build_id}: {status}", flush=True)
            previous = status
        if status in _TERMINAL_BUILD_STATUSES:
            if status != "READY":
                raise RuntimeError(
                    f"build {build_id} failed with {build.get('error_code')}: "
                    f"{build.get('error_summary')}"
                )
            return build
        await asyncio.sleep(1)
    raise RuntimeError(f"build {build_id} did not finish within 300 seconds")


async def _poll_deployment(client: ControlPlaneClient, deployment_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 240
    previous: object = None
    while time.monotonic() < deadline:
        deployment = await client.json("GET", f"/deployments/{deployment_id}", csrf=False)
        status = deployment.get("status")
        if status != previous:
            print(f"deployment {deployment_id}: {status}", flush=True)
            previous = status
        if status in _TERMINAL_DEPLOYMENT_STATUSES:
            if status != "running":
                raise RuntimeError(
                    f"deployment {deployment_id} failed with "
                    f"{deployment.get('error_code')}: {deployment.get('error_summary')}"
                )
            return deployment
        await asyncio.sleep(1)
    raise RuntimeError(f"deployment {deployment_id} did not finish within 240 seconds")


async def _mcp_round_trip(
    *,
    hostname: str,
    bearer_token: str,
    calls: list[tuple[str, dict[str, object]]],
) -> tuple[list[str], list[str], list[dict[str, object]]]:
    inspector = MCPValidationClient(
        bearer_token=bearer_token,
        allowed_hosts=frozenset({hostname}),
        allow_insecure_http=True,
    )
    inspection = await inspector.inspect(f"http://{hostname}/mcp")
    await inspector.close()
    headers = {"Authorization": f"Bearer {bearer_token}"}
    results: list[dict[str, object]] = []
    resources_read: list[str] = []
    async with httpx2.AsyncClient(
        headers=headers,
        timeout=httpx2.Timeout(30),
        follow_redirects=False,
        trust_env=False,
    ) as http:
        transport = streamable_http_client(
            f"http://{hostname}/mcp",
            http_client=http,
            terminate_on_close=True,
        )
        async with Client(transport, read_timeout_seconds=30, cache=None) as mcp:
            tools = await mcp.list_tools(cache_mode="bypass")
            resources = await mcp.list_resources(cache_mode="bypass")
            if resources.resources:
                resource = await mcp.read_resource(resources.resources[0].uri)
                resources_read.append(str(resources.resources[0].uri))
                if not resource.contents:
                    raise RuntimeError("MCP documentation resource was empty")
            for tool_name, arguments in calls:
                result = await mcp.call_tool(tool_name, arguments)
                structured = cast(object, result.structured_content)
                if result.is_error or not isinstance(structured, dict):
                    raise RuntimeError(f"MCP tool {tool_name} returned an error")
                results.append(cast(dict[str, object], structured))
    listed = [str(value) for value in inspection["tools"]]
    if listed != [tool.name for tool in tools.tools]:
        raise RuntimeError("MCP inspection and direct client tool lists differ")
    return listed, resources_read, results


async def _compose(*arguments: str) -> None:
    process = await asyncio.create_subprocess_exec(
        "docker",
        "compose",
        "--env-file",
        ".env",
        "-f",
        "infra/compose.yaml",
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await process.communicate()
    if process.returncode != 0:
        text = output.decode("utf-8", errors="replace")[-4_000:]
        raise RuntimeError(f"docker compose {' '.join(arguments)} failed:\n{text}")


async def _wait_control_plane(client: ControlPlaneClient) -> None:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            ready = await client.json("GET", "/ready", csrf=False)
            if ready.get("ready") is True:
                return
        except (httpx.HTTPError, RuntimeError, ValueError):
            pass
        await asyncio.sleep(1)
    raise RuntimeError("control plane did not become ready after outage recovery")


async def _wait_builder_dependencies(client: ControlPlaneClient) -> None:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            ready = await client.json("GET", "/ready", csrf=False)
            dependencies_value = ready.get("dependencies")
            if ready.get("ready") is True and isinstance(dependencies_value, dict):
                dependencies = cast(dict[str, object], dependencies_value)
                if dependencies.get("milvus") is True and dependencies.get("openrouter") is True:
                    return
        except (httpx.HTTPError, RuntimeError, ValueError):
            pass
        await asyncio.sleep(1)
    raise RuntimeError("builder dependencies did not recover after the outage exercise")


def _tool_name(operations: list[dict[str, object]], operation_id: str) -> str:
    for operation in operations:
        if operation.get("source_operation_id") == operation_id:
            name = operation.get("tool_name")
            if isinstance(name, str) and name:
                return name
    raise RuntimeError(f"generated tool for {operation_id} was not found")


def _assert_export(bundle: bytes, forbidden: tuple[str, ...]) -> list[str]:
    for value in forbidden:
        if value.encode() in bundle:
            raise RuntimeError("export bundle contained forbidden secret material")
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        names = archive.namelist()
        expected = {
            "README.md",
            "build-metadata.json",
            "compose.example.yaml",
            "manifest.json",
            "validation-report.json",
        }
        if set(names) != expected:
            raise RuntimeError("export bundle file set did not match the artifact contract")
        for name in names:
            content = archive.read(name)
            for value in forbidden:
                if value.encode() in content:
                    raise RuntimeError(f"export artifact {name} contained secret material")
        return names


async def run(*, api_base: str, email: str, password: str) -> dict[str, object]:
    upstream = FixtureServer(upstream_app, 9009)
    openrouter = FixtureServer(openrouter_app, 9010)
    client = ControlPlaneClient(api_base)
    upstream_secret = secrets.token_urlsafe(32)
    started = time.monotonic()
    try:
        await upstream.start()
        await openrouter.start()
        await _wait_control_plane(client)
        await client.login(email=email, password=password)
        me = await client.json("GET", "/auth/me", csrf=False)
        if me.get("role") != "admin":
            raise RuntimeError("acceptance workflow requires an administrator")
        model_settings = await client.json(
            "PUT",
            "/settings/models",
            json_body={
                "analysis_model": "mcplica-fixture/analysis",
                "validation_model": "mcplica-fixture/validation",
                "embedding_model": "mcplica-fixture/embedding",
                "include_documentation_in_analysis": True,
            },
        )
        if model_settings.get("include_documentation_in_analysis") is not True:
            raise RuntimeError("documentation-aware model configuration was not persisted")

        project = await client.json(
            "POST",
            "/projects",
            expected=frozenset({201}),
            json_body={
                "name": "MCPlica final acceptance",
                "slug": "final-acceptance",
                "description": "Repository-wide real workflow proof",
                "default_base_url": "http://host.docker.internal:9009/api",
            },
        )
        project_id = str(project["id"])
        hostname = str(project["mcp_hostname"])

        source = await client.json(
            "POST",
            f"/projects/{project_id}/sources",
            expected=frozenset({201}),
            json_body={
                "kind": "openapi",
                "name": "Acceptance OpenAPI",
                "origin_type": "upload",
                "is_primary": True,
            },
        )
        source_id = str(source["id"])
        initial_version = await client.upload(
            f"/projects/{project_id}/sources/{source_id}/versions",
            filename="openapi.json",
            media_type="application/json",
            content=_openapi(updated=False),
        )

        documentation = await client.json(
            "POST",
            f"/projects/{project_id}/sources",
            expected=frozenset({201}),
            json_body={
                "kind": "documentation",
                "name": "Widget operations guide",
                "origin_type": "upload",
                "is_primary": False,
            },
        )
        documentation_id = str(documentation["id"])
        await client.upload(
            f"/projects/{project_id}/sources/{documentation_id}/versions",
            filename="widgets.md",
            media_type="text/markdown",
            content=(
                b"# Widget API\n\nWidgets are durable catalog records. "
                b"Use getWidget for exact identifiers and createWidget for new records.\n"
            ),
        )

        credential = await client.json(
            "POST",
            f"/projects/{project_id}/credentials",
            expected=frozenset({201}),
            json_body={
                "name": "Widget API bearer",
                "scheme_type": "bearer",
                "secret": {"token": upstream_secret},
                "metadata": {"security_scheme": "bearerAuth"},
            },
        )
        if "secret" in credential or "token" in credential:
            raise RuntimeError("credential API redisplayed secret material")

        build_request_started = time.monotonic()
        build_one = await client.json(
            "POST",
            f"/projects/{project_id}/builds",
            expected=frozenset({202}),
            json_body={"trigger": "initial"},
        )
        build_one = await _poll_build(client, str(build_one["id"]))
        build_one_seconds = time.monotonic() - build_request_started
        build_one_id = str(build_one["id"])
        validation_one = await client.json("GET", f"/builds/{build_one_id}/validation", csrf=False)
        if (
            validation_one.get("overall_status") != "pass"
            or float(cast(int | float, validation_one.get("coverage_percent", 0))) != 100
            or validation_one.get("blocking_error_count") != 0
        ):
            raise RuntimeError("initial validation did not prove 100% blocking-clean coverage")
        operations_one = await client.json_list(f"/builds/{build_one_id}/operations")
        ai_runs_one = await client.json_list(f"/builds/{build_one_id}/ai-runs")
        analysis_runs = [item for item in ai_runs_one if item.get("stage") == "analysis"]
        if not analysis_runs or any(item.get("status") != "succeeded" for item in ai_runs_one):
            raise RuntimeError("AI enrichment/semantic validation audit did not succeed")
        if not any(item.get("retrieved_chunk_ids") for item in analysis_runs):
            raise RuntimeError("AI enrichment did not retrieve indexed documentation")
        if not all(operation.get("enriched_description") for operation in operations_one):
            raise RuntimeError("operation enrichment was not applied to every operation")

        manifest_one = await client.json("GET", f"/builds/{build_one_id}/manifest", csrf=False)
        manifest_one_text = json.dumps(manifest_one, sort_keys=True)
        if upstream_secret in manifest_one_text:
            raise RuntimeError("generated manifest contained an upstream secret")
        resources_one = manifest_one.get("resources")
        if not isinstance(resources_one, list) or not resources_one:
            raise RuntimeError("documentation indexing did not produce MCP resources")
        export_names = _assert_export(
            await client.bytes(f"/builds/{build_one_id}/export"),
            (upstream_secret, password),
        )

        await client.json(
            "PUT",
            f"/projects/{project_id}/mcp-access/auth-mode",
            json_body={"mode": "static_bearer"},
        )
        issued = await client.json(
            "POST",
            f"/projects/{project_id}/mcp-access/tokens",
            expected=frozenset({201}),
            json_body={"name": "Final acceptance MCP client"},
        )
        access_token = issued.get("plaintext")
        if not isinstance(access_token, str) or len(access_token) < 32:
            raise RuntimeError("MCP access token was not issued once with sufficient entropy")
        access_after_issue = await client.json(
            "GET", f"/projects/{project_id}/mcp-access", csrf=False
        )
        if access_token in json.dumps(access_after_issue, sort_keys=True):
            raise RuntimeError("MCP access listing redisplayed token plaintext")

        deployment_one_started = time.monotonic()
        deployment_one = await client.json(
            "POST",
            f"/projects/{project_id}/deployments",
            expected=frozenset({202}),
            json_body={"build_id": build_one_id},
        )
        deployment_one = await _poll_deployment(client, str(deployment_one["id"]))
        deployment_one_seconds = time.monotonic() - deployment_one_started
        deployment_one_id = str(deployment_one["id"])
        get_tool = _tool_name(operations_one, "getWidget")
        create_tool = _tool_name(operations_one, "createWidget")
        mcp_started = time.monotonic()
        tools_one, resources_read, call_results = await _mcp_round_trip(
            hostname=hostname,
            bearer_token=access_token,
            calls=[
                (get_tool, {"widget_id": "widget-42", "verbose": True}),
                (create_tool, {"body": {"name": "Created through MCP"}}),
            ],
        )
        mcp_round_trip_seconds = time.monotonic() - mcp_started
        if len(tools_one) != 4 or not resources_read:
            raise RuntimeError("initial MCP tool/resource surface was incomplete")
        expected_calls = (("GET", "/api/widgets/widget-42"), ("POST", "/api/widgets"))
        for result, (method, path) in zip(call_results, expected_calls, strict=True):
            if (
                result.get("method") != method
                or result.get("path") != path
                or result.get("authorization") != f"Bearer {upstream_secret}"
            ):
                raise RuntimeError("MCP call did not preserve exact mapping/authentication")

        # Prove the serving plane remains live with the AI fixture, Milvus, API, and
        # builder worker all unavailable. PostgreSQL/Redis stay up only because they
        # are irrelevant to the runtime and needed for subsequent recovery/build steps.
        await openrouter.stop()
        await _compose("stop", "api", "builder-worker", "milvus")
        _, _, outage_results = await _mcp_round_trip(
            hostname=hostname,
            bearer_token=access_token,
            calls=[(get_tool, {"widget_id": "outage-proof"})],
        )
        if outage_results[0].get("path") != "/api/widgets/outage-proof":
            raise RuntimeError("runtime failed while builder-side dependencies were unavailable")
        openrouter = FixtureServer(openrouter_app, 9010)
        await openrouter.start()
        await _compose(
            "up",
            "--detach",
            "--wait",
            "--wait-timeout",
            "180",
            "milvus",
            "api",
            "builder-worker",
        )
        await _wait_control_plane(client)
        await _wait_builder_dependencies(client)

        updated_version = await client.upload(
            f"/projects/{project_id}/sources/{source_id}/versions",
            filename="openapi-v2.json",
            media_type="application/json",
            content=_openapi(updated=True),
        )
        if updated_version.get("content_sha256") == initial_version.get("content_sha256"):
            raise RuntimeError("source update did not create a new immutable content version")
        build_two = await client.json(
            "POST",
            f"/projects/{project_id}/rebuild",
            expected=frozenset({202}),
        )
        build_two = await _poll_build(client, str(build_two["id"]))
        build_two_id = str(build_two["id"])
        if build_two.get("trigger") != "manual_rebuild":
            raise RuntimeError("source update rebuild did not retain the requested trigger")
        diff = await client.json("GET", f"/builds/{build_two_id}/diff", csrf=False)
        if not diff.get("added_operations"):
            raise RuntimeError("source-change rebuild diff did not report the added operation")
        validation_two = await client.json("GET", f"/builds/{build_two_id}/validation", csrf=False)
        if float(cast(int | float, validation_two.get("coverage_percent", 0))) != 100:
            raise RuntimeError("updated build did not retain 100% expected coverage")
        operations_two = await client.json_list(f"/builds/{build_two_id}/operations")
        search_tool = _tool_name(operations_two, "searchWidgets")

        deployment_two = await client.json(
            "POST",
            f"/projects/{project_id}/deployments",
            expected=frozenset({202}),
            json_body={"build_id": build_two_id},
        )
        deployment_two = await _poll_deployment(client, str(deployment_two["id"]))
        deployment_two_id = str(deployment_two["id"])
        old_after_redeploy = await client.json(
            "GET", f"/deployments/{deployment_one_id}", csrf=False
        )
        _assert_superseded_before_running(old_after_redeploy, deployment_two)
        tools_two, _, search_result = await _mcp_round_trip(
            hostname=hostname,
            bearer_token=access_token,
            calls=[(search_tool, {})],
        )
        if search_tool not in tools_two or search_result[0].get("path") != "/api/widgets/search":
            raise RuntimeError("redeployed runtime did not serve the source update")

        rollback = await client.json(
            "POST",
            f"/projects/{project_id}/rollback",
            expected=frozenset({202}),
            json_body={"target_deployment_id": deployment_one_id},
        )
        rollback = await _poll_deployment(client, str(rollback["id"]))
        rollback_id = str(rollback["id"])
        if str(rollback.get("build_id")) != build_one_id:
            raise RuntimeError("rollback did not reference the immutable original build")
        replaced_after_rollback = await client.json(
            "GET", f"/deployments/{deployment_two_id}", csrf=False
        )
        _assert_superseded_before_running(replaced_after_rollback, rollback)
        rollback_tools, _, rollback_result = await _mcp_round_trip(
            hostname=hostname,
            bearer_token=access_token,
            calls=[(get_tool, {"widget_id": "rolled-back"})],
        )
        if (
            search_tool in rollback_tools
            or rollback_result[0].get("path") != "/api/widgets/rolled-back"
        ):
            raise RuntimeError("rollback did not restore the original MCP surface")
        project_after_rollback = await client.json("GET", f"/projects/{project_id}", csrf=False)
        if (
            str(project_after_rollback.get("active_build_id")) != build_one_id
            or str(project_after_rollback.get("active_deployment_id")) != rollback_id
        ):
            raise RuntimeError("project active references were not atomically rolled back")

        return {
            "status": "passed",
            "project_id": project_id,
            "source_versions": [str(initial_version["id"]), str(updated_version["id"])],
            "builds": [build_one_id, build_two_id],
            "deployments": [deployment_one_id, deployment_two_id, rollback_id],
            "initial_tool_count": len(tools_one),
            "updated_tool_count": len(tools_two),
            "rollback_tool_count": len(rollback_tools),
            "documentation_resources_read": len(resources_read),
            "initial_coverage_percent": validation_one["coverage_percent"],
            "updated_coverage_percent": validation_two["coverage_percent"],
            "diff_added_operations": len(cast(list[object], diff["added_operations"])),
            "export_files": export_names,
            "builder_outage_runtime_call": "passed",
            "build_one_seconds": round(build_one_seconds, 3),
            "deployment_one_seconds": round(deployment_one_seconds, 3),
            "mcp_round_trip_seconds": round(mcp_round_trip_seconds, 3),
            "total_seconds": round(time.monotonic() - started, 3),
        }
    finally:
        await client.close()
        await openrouter.stop()
        await upstream.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-base",
        default=os.getenv("E2E_API_BASE", "http://127.0.0.1:8000/api/v1"),
    )
    parser.add_argument(
        "--email",
        default=os.getenv("E2E_ADMIN_EMAIL", "admin@admin.com"),
    )
    args = parser.parse_args()
    password = os.getenv("E2E_ADMIN_PASSWORD", "admin@321")
    result = asyncio.run(run(api_base=args.api_base, email=args.email, password=password))
    print(json.dumps(result, sort_keys=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
