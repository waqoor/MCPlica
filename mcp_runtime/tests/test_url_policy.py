import asyncio
from collections.abc import Iterable

import httpcore
import httpx
import pytest
from mcp_contracts import ServerDefinition
from pydantic import AnyHttpUrl

from app.clients.pinned_transport import PolicyAsyncHttpTransport, PolicyNetworkBackend
from app.executor.errors import DestinationPolicyError
from app.security.url_policy import UpstreamUrlPolicy


class _RecordingBackend(httpcore.AsyncNetworkBackend):
    def __init__(self) -> None:
        self.hosts: list[str] = []

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        del port, timeout, local_address, socket_options
        self.hosts.append(host)
        raise httpcore.ConnectError("test connection is intentionally disabled")

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        del path, timeout, socket_options
        raise AssertionError("Unix sockets must not be used")

    async def sleep(self, seconds: float) -> None:
        del seconds


@pytest.mark.asyncio
async def test_private_and_special_destinations_are_fail_closed() -> None:
    policy = UpstreamUrlPolicy(
        [ServerDefinition(id="private", url=AnyHttpUrl("http://127.0.0.1:9000"))]
    )
    with pytest.raises(DestinationPolicyError):
        await policy.validate_before_connect("http://127.0.0.1:9000/path")


@pytest.mark.asyncio
async def test_named_development_destination_requires_explicit_mode_and_host() -> None:
    policy = UpstreamUrlPolicy(
        [ServerDefinition(id="private", url=AnyHttpUrl("http://127.0.0.1:9000"))],
        allowed_development_hosts=["127.0.0.1"],
        development_mode=True,
    )
    await policy.validate_before_connect("http://127.0.0.1:9000/path")

    with pytest.raises(DestinationPolicyError):
        policy.assert_url_is_allowlisted("http://127.0.0.1:9001/path")


@pytest.mark.asyncio
async def test_named_development_destination_may_resolve_to_private_bridge_address() -> None:
    async def resolver(_: str, __: int) -> Iterable[str]:
        return ["192.168.65.254"]

    endpoint = "http://host.docker.internal:9009"
    policy = UpstreamUrlPolicy(
        [ServerDefinition(id="docker-host", url=AnyHttpUrl(endpoint))],
        allowed_development_hosts=["host.docker.internal"],
        development_mode=True,
        resolver=resolver,
    )

    await policy.validate_before_connect(f"{endpoint}/api/widgets/widget-42")

    production_policy = UpstreamUrlPolicy(
        [ServerDefinition(id="docker-host", url=AnyHttpUrl(endpoint))],
        allowed_development_hosts=["host.docker.internal"],
        development_mode=False,
        resolver=resolver,
    )
    with pytest.raises(DestinationPolicyError):
        await production_policy.validate_before_connect(f"{endpoint}/api/widgets/widget-42")


@pytest.mark.asyncio
async def test_socket_connects_to_validated_ip_without_second_system_resolution() -> None:
    async def resolver(_: str, __: int) -> Iterable[str]:
        return ["93.184.216.34"]

    policy = UpstreamUrlPolicy(
        [ServerDefinition(id="api", url=AnyHttpUrl("https://api.example.com"))],
        resolver=resolver,
    )
    backend = _RecordingBackend()

    with pytest.raises(httpcore.ConnectError):
        await PolicyNetworkBackend(policy, backend=backend).connect_tcp(
            "api.example.com", 443, timeout=1.0
        )

    assert backend.hosts == ["93.184.216.34"]


@pytest.mark.asyncio
async def test_dns_rebinding_is_rejected_at_the_socket_boundary() -> None:
    answers = iter((["93.184.216.34"], ["127.0.0.1"]))

    async def resolver(_: str, __: int) -> Iterable[str]:
        return next(answers)

    endpoint = "https://api.example.com/resource"
    policy = UpstreamUrlPolicy(
        [ServerDefinition(id="api", url=AnyHttpUrl("https://api.example.com"))],
        resolver=resolver,
    )
    backend = _RecordingBackend()
    await policy.validate_before_connect(endpoint)

    with pytest.raises(DestinationPolicyError):
        await PolicyNetworkBackend(policy, backend=backend).connect_tcp(
            "api.example.com", 443, timeout=1.0
        )

    assert backend.hosts == []


@pytest.mark.asyncio
async def test_policy_transport_executes_through_the_pinned_socket() -> None:
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readuntil(b"\r\n\r\n")
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    socket = server.sockets[0]
    port = int(socket.getsockname()[1])
    endpoint = f"http://127.0.0.1:{port}"
    policy = UpstreamUrlPolicy(
        [ServerDefinition(id="local", url=AnyHttpUrl(endpoint))],
        allowed_development_hosts=["127.0.0.1"],
        development_mode=True,
    )
    client = httpx.AsyncClient(
        transport=PolicyAsyncHttpTransport(
            policy,
            verify=False,
            max_connections=2,
            max_keepalive_connections=1,
        ),
        trust_env=False,
    )
    try:
        response = await client.get(f"{endpoint}/ready")
        assert response.status_code == 200
        assert response.text == "ok"
    finally:
        await client.aclose()
        server.close()
        await server.wait_closed()
