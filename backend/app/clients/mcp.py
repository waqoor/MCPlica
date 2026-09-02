import asyncio
import hashlib
import ipaddress
import socket
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import NotRequired, TypedDict, cast
from urllib.parse import urlsplit, urlunsplit

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import LATEST_PROTOCOL_VERSION, Resource, Tool
from mcp_contracts import MCPManifest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.clients.base import AsyncClient
from app.core.exceptions import ProtocolValidationError

AddressResolver = Callable[[str, int], Awaitable[Iterable[str]]]
_MAX_RESOLVED_ADDRESSES = 32
_MAX_INSPECTION_ITEMS = 100_000
_MAX_INSPECTION_RESPONSE_BYTES = 50_000_000


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
    runtime_version: NotRequired[str]
    manifest_sha256: NotRequired[str]
    exercised_tool_count: NotRequired[int]
    exercised_tools: NotRequired[list[str]]
    request_mapping_count: NotRequired[int]


class _RuntimeCandidateInspection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime_version: str = Field(min_length=1, max_length=64)
    protocol_version: str = Field(min_length=1, max_length=64)
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    tool_count: int = Field(ge=0, le=_MAX_INSPECTION_ITEMS)
    tools: list[str] = Field(max_length=_MAX_INSPECTION_ITEMS)
    resource_count: int = Field(ge=0, le=_MAX_INSPECTION_ITEMS)
    resources: list[str] = Field(max_length=_MAX_INSPECTION_ITEMS)
    exercised_tool_count: int = Field(ge=0, le=_MAX_INSPECTION_ITEMS)
    exercised_tools: list[str] = Field(max_length=_MAX_INSPECTION_ITEMS)
    request_mapping_count: int = Field(ge=0, le=_MAX_INSPECTION_ITEMS)

    @model_validator(mode="after")
    def counts_match_payloads(self) -> "_RuntimeCandidateInspection":
        if self.tool_count != len(self.tools) or len(set(self.tools)) != len(self.tools):
            raise ValueError("runtime validator returned an invalid tool listing")
        if self.resource_count != len(self.resources) or len(set(self.resources)) != len(
            self.resources
        ):
            raise ValueError("runtime validator returned an invalid resource listing")
        if self.exercised_tool_count != len(self.exercised_tools) or not set(
            self.exercised_tools
        ) <= set(self.tools):
            raise ValueError("runtime validator returned invalid exercise evidence")
        if self.request_mapping_count != self.exercised_tool_count:
            raise ValueError("runtime validator returned inconsistent mapping evidence")
        return self


class MCPValidationClient(AsyncClient):
    """Validate MCP payloads through the pinned official SDK boundary."""

    def __init__(
        self,
        endpoint: str | None = None,
        *,
        validator_endpoint: str | None = None,
        bearer_token: str | None = None,
        timeout_seconds: float = 30.0,
        max_pages: int = 100,
        max_items: int = _MAX_INSPECTION_ITEMS,
        max_response_bytes: int = _MAX_INSPECTION_RESPONSE_BYTES,
        allowed_hosts: frozenset[str] = frozenset(),
        allow_insecure_http: bool = False,
        resolver: AddressResolver = _system_resolver,
        validator_transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("MCP timeout must be positive")
        if (
            max_pages < 1
            or not 1 <= max_items <= _MAX_INSPECTION_ITEMS
            or not 1_024 <= max_response_bytes <= _MAX_INSPECTION_RESPONSE_BYTES
        ):
            raise ValueError("MCP inspection bounds are outside supported limits")
        self._endpoint = endpoint
        self._validator_endpoint = (
            self._validate_validator_endpoint(validator_endpoint)
            if validator_endpoint is not None
            else None
        )
        self._bearer_token = self._validate_token(bearer_token)
        self._timeout_seconds = timeout_seconds
        self._max_pages = max_pages
        self._max_items = max_items
        self._max_response_bytes = max_response_bytes
        self._allowed_hosts = frozenset(self._normalize_hostname(host) for host in allowed_hosts)
        self._allow_insecure_http = allow_insecure_http
        self._resolver = resolver
        self._validator_transport = validator_transport

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

    async def inspect_manifest(
        self,
        manifest: MCPManifest,
        *,
        runtime_version: str,
    ) -> MCPInspection:
        """Execute a candidate through the separately pinned generic-runtime validator."""

        if self._validator_endpoint is None:
            raise ProtocolValidationError("Pinned generic-runtime validation is not configured")
        payload = manifest.model_dump_json(by_alias=True).encode("utf-8")
        expected_sha256 = hashlib.sha256(payload).hexdigest()
        try:
            async with asyncio.timeout(self._timeout_seconds):
                async with httpx2.AsyncClient(
                    follow_redirects=False,
                    timeout=httpx2.Timeout(self._timeout_seconds),
                    trust_env=False,
                    transport=(
                        self._validator_transport
                        or _BoundedHttpTransport(max_bytes=self._max_response_bytes)
                    ),
                ) as http:
                    response = await http.post(
                        self._validator_endpoint,
                        content=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    body = await response.aread()
        except TimeoutError as exc:
            raise ProtocolValidationError("Pinned generic-runtime validation timed out") from exc
        except (httpx2.HTTPError, httpx2.StreamError) as exc:
            raise ProtocolValidationError(
                "Pinned generic-runtime validator could not be reached"
            ) from exc
        if response.status_code != 200:
            raise ProtocolValidationError("Pinned generic runtime rejected the generated manifest")
        try:
            inspected = _RuntimeCandidateInspection.model_validate_json(body)
        except ValidationError as exc:
            raise ProtocolValidationError(
                "Pinned generic-runtime validator returned invalid evidence"
            ) from exc
        if (
            inspected.tool_count > self._max_items
            or inspected.resource_count > self._max_items
            or inspected.exercised_tool_count > self._max_items
        ):
            raise ProtocolValidationError(
                "Pinned generic-runtime validator exceeded its configured item limit"
            )
        enabled_names = [tool.name for tool in manifest.enabled_tools()]
        resource_uris = [str(resource.uri) for resource in manifest.resources]
        if inspected.runtime_version != runtime_version:
            raise ProtocolValidationError("Pinned generic-runtime version does not match the build")
        if inspected.protocol_version != LATEST_PROTOCOL_VERSION:
            raise ProtocolValidationError(
                "Pinned generic runtime did not validate the latest MCP protocol revision"
            )
        if inspected.manifest_sha256 != expected_sha256:
            raise ProtocolValidationError(
                "Pinned generic runtime validated different manifest bytes"
            )
        if inspected.tools != enabled_names or inspected.resources != resource_uris:
            raise ProtocolValidationError("Pinned generic-runtime listing changed the manifest")
        if (
            inspected.exercised_tool_count != len(enabled_names)
            or inspected.exercised_tools != enabled_names
        ):
            raise ProtocolValidationError(
                "Pinned generic runtime did not exercise every enabled request mapping"
            )
        return cast(MCPInspection, inspected.model_dump(mode="python"))

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
    def _validate_validator_endpoint(value: str) -> str:
        if not value or len(value) > 2_048 or any(character in value for character in "\r\n\x00"):
            raise ValueError("runtime validator endpoint is invalid")
        parsed = urlsplit(value)
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("runtime validator endpoint is invalid") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path != "/validate"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("runtime validator endpoint must be an HTTP(S) /validate URL")
        return value

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
