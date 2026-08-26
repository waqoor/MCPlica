import asyncio
import ipaddress
import socket
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import TypedDict, cast
from urllib.parse import urlsplit, urlunsplit

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import ListResourcesResult, ListToolsResult, Resource, Tool
from mcp_contracts import MCPManifest
from pydantic import ValidationError as PydanticValidationError

from app.clients.base import AsyncClient
from app.core.exceptions import ProtocolValidationError

AddressResolver = Callable[[str, int], Awaitable[Iterable[str]]]
_MAX_RESOLVED_ADDRESSES = 32


async def _system_resolver(hostname: str, port: int) -> Iterable[str]:
    loop = asyncio.get_running_loop()
    try:
        records = await loop.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise ProtocolValidationError("MCP endpoint hostname could not be resolved") from exc
    return {record[4][0].split("%", 1)[0] for record in records if isinstance(record[4][0], str)}


@dataclass(frozen=True, slots=True)
class _PinnedEndpoint:
    url: str
    authority: str
    hostname: str


class _BoundedResponseStream(httpx2.AsyncByteStream):
    def __init__(self, stream: httpx2.AsyncByteStream, max_bytes: int) -> None:
        self._stream = stream
        self._max_bytes = max_bytes
        self._received = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self._stream:
            self._received += len(chunk)
            if self._received > self._max_bytes:
                raise httpx2.StreamError("MCP endpoint response exceeded its byte limit")
            yield chunk

    async def aclose(self) -> None:
        await self._stream.aclose()


class _BoundedHttpTransport(httpx2.AsyncBaseTransport):
    def __init__(self, *, max_bytes: int, timeout_connections: int = 10) -> None:
        self._max_bytes = max_bytes
        self._transport = httpx2.AsyncHTTPTransport(
            trust_env=False,
            limits=httpx2.Limits(
                max_connections=timeout_connections,
                max_keepalive_connections=min(5, timeout_connections),
            ),
        )

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        response = await self._transport.handle_async_request(request)
        declared = response.headers.get("content-length")
        if declared is not None:
            try:
                declared_bytes = int(declared)
            except ValueError as exc:
                await response.aclose()
                raise ProtocolValidationError(
                    "MCP endpoint returned an invalid body length"
                ) from exc
            if declared_bytes < 0 or declared_bytes > self._max_bytes:
                await response.aclose()
                raise ProtocolValidationError("MCP endpoint response exceeded its byte limit")
        if not isinstance(response.stream, httpx2.AsyncByteStream):
            await response.aclose()
            raise ProtocolValidationError("MCP endpoint returned an invalid response stream")
        return httpx2.Response(
            status_code=response.status_code,
            headers=response.headers,
            stream=_BoundedResponseStream(response.stream, self._max_bytes),
            extensions=cast(
                dict[str, object],
                response.extensions,  # pyright: ignore[reportUnknownMemberType]
            ),
        )

    async def aclose(self) -> None:
        await self._transport.aclose()


class MCPInspection(TypedDict):
    protocol_version: str | None
    tool_count: int
    tools: list[str]
    resource_count: int
    resources: list[str]


class MCPValidationClient(AsyncClient):
    """Validate MCP payloads through the pinned official SDK boundary."""

    def __init__(
        self,
        endpoint: str | None = None,
        *,
        bearer_token: str | None = None,
        timeout_seconds: float = 30.0,
        max_pages: int = 100,
        max_items: int = 10_000,
        max_response_bytes: int = 10_000_000,
        allowed_hosts: frozenset[str] = frozenset(),
        allow_insecure_http: bool = False,
        resolver: AddressResolver = _system_resolver,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("MCP timeout must be positive")
        if max_pages < 1 or max_items < 1 or not 1_024 <= max_response_bytes <= 50_000_000:
            raise ValueError("MCP inspection bounds must be positive")
        self._endpoint = endpoint
        self._bearer_token = self._validate_token(bearer_token)
        self._timeout_seconds = timeout_seconds
        self._max_pages = max_pages
        self._max_items = max_items
        self._max_response_bytes = max_response_bytes
        self._allowed_hosts = frozenset(self._normalize_hostname(host) for host in allowed_hosts)
        self._allow_insecure_http = allow_insecure_http
        self._resolver = resolver

    async def health(self) -> bool:
        if self._endpoint is None:
            return False
        try:
            await self.inspect(self._endpoint, bearer_token=self._bearer_token)
        except ProtocolValidationError:
            return False
        return True

    async def inspect(
        self,
        endpoint: str,
        *,
        bearer_token: str | None = None,
    ) -> MCPInspection:
        pinned_endpoint = await self._pin_endpoint(self._validate_endpoint(endpoint))
        token = self._validate_token(bearer_token)
        if token is None:
            token = self._bearer_token
        headers: dict[str, str] = {
            "Host": pinned_endpoint.authority,
            "Connection": "close",
        }
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"

        async def preserve_tls_identity(request: httpx2.Request) -> None:
            request.extensions["sni_hostname"] = pinned_endpoint.hostname

        try:
            async with asyncio.timeout(self._timeout_seconds):
                async with httpx2.AsyncClient(
                    headers=headers,
                    follow_redirects=False,
                    timeout=httpx2.Timeout(self._timeout_seconds),
                    limits=httpx2.Limits(
                        max_connections=10,
                        max_keepalive_connections=5,
                    ),
                    trust_env=False,
                    event_hooks={"request": [preserve_tls_identity]},
                    transport=_BoundedHttpTransport(max_bytes=self._max_response_bytes),
                ) as http:
                    transport = streamable_http_client(
                        pinned_endpoint.url,
                        http_client=http,
                        terminate_on_close=True,
                    )
                    async with Client(
                        transport,
                        read_timeout_seconds=self._timeout_seconds,
                        cache=None,
                    ) as client:
                        tools = await self._list_tools(client)
                        resources = await self._list_resources(client)
                        return {
                            "protocol_version": client.protocol_version,
                            "tool_count": len(tools),
                            "tools": [tool.name for tool in tools],
                            "resource_count": len(resources),
                            "resources": [str(resource.uri) for resource in resources],
                        }
        except TimeoutError as exc:
            raise ProtocolValidationError("MCP endpoint inspection timed out") from exc
        except ProtocolValidationError:
            raise
        except Exception as exc:
            raise ProtocolValidationError(
                "MCP endpoint did not complete protocol validation"
            ) from exc

    async def inspect_manifest(self, manifest: MCPManifest) -> MCPInspection:
        """Round-trip generated list payloads using the official MCP models.

        Build validation happens before a runtime exists. This catches SDK-level
        protocol incompatibilities without introducing another manifest model or
        pretending that an endpoint has already been deployed.
        """

        enabled_tools = manifest.enabled_tools()
        try:
            if len({tool.name for tool in enabled_tools}) != len(enabled_tools):
                raise ValueError("duplicate tool names")
            if len({str(resource.uri) for resource in manifest.resources}) != len(
                manifest.resources
            ):
                raise ValueError("duplicate resource URIs")
            tools = [
                Tool.model_validate(
                    {
                        "name": tool.name,
                        "title": tool.title,
                        "description": tool.description,
                        "inputSchema": tool.input_schema,
                        "outputSchema": tool.output_schema,
                    }
                )
                for tool in enabled_tools
            ]
            resources = [
                Resource.model_validate(
                    {
                        "name": resource.name,
                        "title": resource.name,
                        "uri": resource.uri,
                        "description": resource.description,
                        "mimeType": resource.mime_type,
                        "size": len(resource.content.encode("utf-8")),
                    }
                )
                for resource in manifest.resources
            ]
            tool_result = ListToolsResult(tools=tools)
            resource_result = ListResourcesResult(resources=resources)
            decoded_tools = ListToolsResult.model_validate_json(tool_result.model_dump_json())
            decoded_resources = ListResourcesResult.model_validate_json(
                resource_result.model_dump_json()
            )
            for source, decoded in zip(enabled_tools, decoded_tools.tools, strict=True):
                if (
                    source.name != decoded.name
                    or source.title != decoded.title
                    or source.description != decoded.description
                    or source.input_schema != decoded.input_schema
                    or source.output_schema != decoded.output_schema
                ):
                    raise ValueError("tool contract changed during MCP serialization")
            for source, decoded in zip(
                manifest.resources,
                decoded_resources.resources,
                strict=True,
            ):
                if (
                    source.name != decoded.name
                    or str(source.uri) != str(decoded.uri)
                    or source.description != decoded.description
                    or source.mime_type != decoded.mime_type
                    or len(source.content.encode("utf-8")) != decoded.size
                ):
                    raise ValueError("resource contract changed during MCP serialization")
        except (PydanticValidationError, TypeError, ValueError) as exc:
            raise ProtocolValidationError(
                "Generated manifest is incompatible with the pinned MCP SDK"
            ) from exc
        return {
            "protocol_version": None,
            "tool_count": len(decoded_tools.tools),
            "tools": [tool.name for tool in decoded_tools.tools],
            "resource_count": len(decoded_resources.resources),
            "resources": [str(resource.uri) for resource in decoded_resources.resources],
        }

    async def _list_tools(self, client: Client) -> list[Tool]:
        values: list[Tool] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        for _ in range(self._max_pages):
            page = await client.list_tools(cursor=cursor, cache_mode="bypass")
            values.extend(page.tools)
            self._check_collection(values, label="tools", keys=[tool.name for tool in values])
            cursor = page.next_cursor
            if cursor is None:
                return values
            if cursor in seen_cursors:
                raise ProtocolValidationError("MCP tools pagination repeated a cursor")
            seen_cursors.add(cursor)
        raise ProtocolValidationError("MCP tools pagination exceeded its configured limit")

    async def _list_resources(self, client: Client) -> list[Resource]:
        values: list[Resource] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        for _ in range(self._max_pages):
            page = await client.list_resources(cursor=cursor, cache_mode="bypass")
            values.extend(page.resources)
            self._check_collection(
                values,
                label="resources",
                keys=[str(resource.uri) for resource in values],
            )
            cursor = page.next_cursor
            if cursor is None:
                return values
            if cursor in seen_cursors:
                raise ProtocolValidationError("MCP resources pagination repeated a cursor")
            seen_cursors.add(cursor)
        raise ProtocolValidationError("MCP resources pagination exceeded its configured limit")

    def _check_collection(self, values: Sequence[object], *, label: str, keys: list[str]) -> None:
        if len(values) > self._max_items:
            raise ProtocolValidationError(f"MCP {label} exceeded its configured item limit")
        if len(set(keys)) != len(keys):
            raise ProtocolValidationError(f"MCP {label} contained duplicate identifiers")

    def _validate_endpoint(self, endpoint: str) -> str:
        if (
            not endpoint
            or len(endpoint) > 2_048
            or any(character in endpoint for character in "\r\n\x00")
        ):
            raise ProtocolValidationError("MCP endpoint URL is invalid")
        parsed = urlsplit(endpoint)
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ProtocolValidationError("MCP endpoint URL is invalid") from exc
        try:
            host = self._normalize_hostname(parsed.hostname or "")
        except ValueError as exc:
            raise ProtocolValidationError("MCP endpoint URL is invalid") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ProtocolValidationError("MCP endpoint URL is invalid")
        if parsed.scheme != "https" and not self._allow_insecure_http:
            raise ProtocolValidationError("MCP endpoint must use HTTPS")
        if self._allowed_hosts and host not in self._allowed_hosts:
            raise ProtocolValidationError("MCP endpoint host is not allowed")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global and host not in self._allowed_hosts:
            raise ProtocolValidationError("MCP endpoint address is not allowed")
        return endpoint

    async def _pin_endpoint(self, endpoint: str) -> _PinnedEndpoint:
        parsed = urlsplit(endpoint)
        assert parsed.hostname is not None
        hostname = self._normalize_hostname(parsed.hostname)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            literal = ipaddress.ip_address(hostname)
        except ValueError:
            try:
                raw_addresses = await self._resolver(hostname, port)
                addresses = {
                    ipaddress.ip_address(value.split("%", 1)[0]) for value in raw_addresses
                }
            except ProtocolValidationError:
                raise
            except (OSError, ValueError) as exc:
                raise ProtocolValidationError("MCP endpoint hostname is invalid") from exc
        else:
            addresses = {literal}
        if not addresses:
            raise ProtocolValidationError("MCP endpoint hostname resolved to no addresses")
        if len(addresses) > _MAX_RESOLVED_ADDRESSES:
            raise ProtocolValidationError("MCP endpoint hostname resolved to too many addresses")
        if hostname not in self._allowed_hosts and any(
            not address.is_global for address in addresses
        ):
            raise ProtocolValidationError("MCP endpoint resolved to a blocked address")
        address = sorted(addresses, key=lambda value: (value.version, int(value)))[0]
        pinned_authority = f"[{address}]" if address.version == 6 else str(address)
        if parsed.port is not None:
            pinned_authority = f"{pinned_authority}:{parsed.port}"
        host_authority = f"[{hostname}]" if ":" in hostname else hostname
        authority = host_authority if parsed.port is None else f"{host_authority}:{parsed.port}"
        return _PinnedEndpoint(
            url=urlunsplit(
                (
                    parsed.scheme,
                    pinned_authority,
                    parsed.path,
                    "",
                    "",
                )
            ),
            authority=authority,
            hostname=hostname,
        )

    @staticmethod
    def _normalize_hostname(value: str) -> str:
        candidate = value.strip().rstrip(".")
        if (
            not candidate
            or len(candidate) > 253
            or any(character in candidate for character in "/?#@\\\r\n\x00")
        ):
            raise ValueError("hostname is invalid")
        try:
            return candidate.encode("idna").decode("ascii").casefold()
        except UnicodeError as exc:
            raise ValueError("hostname is invalid") from exc

    @staticmethod
    def _validate_token(token: str | None) -> str | None:
        if token is None:
            return None
        value = token.strip()
        if not value or len(value) > 8_192 or any(character in value for character in "\r\n\x00"):
            raise ProtocolValidationError("MCP bearer token is invalid")
        return value
