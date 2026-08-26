import time
from collections.abc import AsyncIterable, AsyncIterator, Iterable
from typing import NoReturn, cast

import httpcore
import httpx

from app.security.url_policy import UpstreamUrlPolicy


def _raise_httpx_transport_error(
    error: Exception,
    *,
    request: httpx.Request,
) -> NoReturn:
    if isinstance(error, httpcore.TimeoutException):
        raise httpx.TimeoutException("HTTP operation timed out", request=request) from error
    raise httpx.TransportError("HTTP transport failed", request=request) from error


class PolicyNetworkBackend(httpcore.AsyncNetworkBackend):
    """Resolve and connect in one policy boundary so DNS cannot rebind the socket."""

    def __init__(
        self,
        policy: UpstreamUrlPolicy,
        *,
        backend: httpcore.AsyncNetworkBackend | None = None,
    ) -> None:
        self._policy = policy
        self._backend = (
            backend
            if backend is not None
            else cast(httpcore.AsyncNetworkBackend, httpcore.AnyIOBackend())
        )

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        addresses = await self._policy.resolve_for_connection(host, port)
        deadline = time.monotonic() + timeout if timeout is not None else None
        last_error: httpcore.ConnectError | httpcore.ConnectTimeout | None = None
        for address in addresses:
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            if remaining == 0.0:
                break
            try:
                return await self._backend.connect_tcp(
                    address,
                    port,
                    timeout=remaining,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise httpcore.ConnectTimeout("Validated upstream addresses could not be reached")

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        del path, timeout, socket_options
        raise httpcore.ConnectError("Unix sockets are forbidden for runtime HTTP clients")

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


class _PolicyResponseStream(httpx.AsyncByteStream):
    def __init__(
        self,
        stream: AsyncIterable[bytes],
        request: httpx.Request,
    ) -> None:
        self._stream = stream
        self._request = request

    async def __aiter__(self) -> AsyncIterator[bytes]:
        try:
            async for chunk in self._stream:
                yield chunk
        except (httpcore.TimeoutException, httpcore.NetworkError, httpcore.ProtocolError) as exc:
            _raise_httpx_transport_error(exc, request=self._request)

    async def aclose(self) -> None:
        close = getattr(self._stream, "aclose", None)
        if close is not None:
            await close()


class PolicyAsyncHttpTransport(httpx.AsyncBaseTransport):
    """HTTPX transport with pooled, hostname-keyed connections pinned after policy DNS checks."""

    def __init__(
        self,
        policy: UpstreamUrlPolicy,
        *,
        verify: bool,
        max_connections: int,
        max_keepalive_connections: int,
        keepalive_expiry: float = 30.0,
    ) -> None:
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=httpx.create_ssl_context(verify=verify, trust_env=False),
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
            keepalive_expiry=keepalive_expiry,
            retries=0,
            network_backend=PolicyNetworkBackend(policy),
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if not isinstance(request.stream, httpx.AsyncByteStream):
            raise TypeError("Policy HTTP transport requires an asynchronous request stream")
        core_request = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        try:
            response = await self._pool.handle_async_request(core_request)
        except (
            httpcore.TimeoutException,
            httpcore.NetworkError,
            httpcore.ProtocolError,
            httpcore.ProxyError,
        ) as exc:
            _raise_httpx_transport_error(exc, request=request)
        if not isinstance(response.stream, AsyncIterable):
            raise TypeError("HTTP core returned an invalid asynchronous response stream")
        return httpx.Response(
            status_code=response.status,
            headers=response.headers,
            stream=_PolicyResponseStream(response.stream, request),
            extensions=cast(
                dict[str, object],
                response.extensions,  # pyright: ignore[reportUnknownMemberType]
            ),
        )

    async def aclose(self) -> None:
        await self._pool.aclose()
