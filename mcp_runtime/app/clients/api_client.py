import asyncio
import json
from dataclasses import dataclass
from urllib.parse import quote, urlencode

import httpx

from app.clients.pinned_transport import PolicyAsyncHttpTransport
from app.clients.response_reader import read_bounded_body
from app.executor.errors import (
    UpstreamConnectionError,
    UpstreamContentTypeError,
    UpstreamRequestTooLargeError,
    UpstreamTimeoutError,
)
from app.executor.request_builder import BuiltRequest, QueryParameter
from app.security.url_policy import UpstreamUrlPolicy


@dataclass(frozen=True, slots=True)
class UpstreamResult:
    status_code: int
    content_type: str
    data: object

    @property
    def is_error(self) -> bool:
        return self.status_code >= 300


class ApiClient:
    def __init__(
        self,
        policy: UpstreamUrlPolicy,
        *,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        keepalive_expiry_seconds: float = 30.0,
        connect_timeout_seconds: float = 10.0,
        read_timeout_seconds: float = 30.0,
        write_timeout_seconds: float = 30.0,
        pool_timeout_seconds: float = 10.0,
        max_request_bytes: int = 10_000_000,
        tls_verify: bool = True,
        trust_env: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if trust_env:
            raise ValueError("Runtime HTTP clients cannot inherit environment proxies")
        self.policy = policy
        self.max_request_bytes = max_request_bytes
        effective_transport = transport or PolicyAsyncHttpTransport(
            policy,
            verify=tls_verify,
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
            keepalive_expiry=keepalive_expiry_seconds,
        )
        self.client = httpx.AsyncClient(
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive_connections,
                keepalive_expiry=keepalive_expiry_seconds,
            ),
            timeout=httpx.Timeout(
                connect=connect_timeout_seconds,
                read=read_timeout_seconds,
                write=write_timeout_seconds,
                pool=pool_timeout_seconds,
            ),
            transport=effective_transport,
        )

    async def execute(
        self,
        request: BuiltRequest,
        *,
        timeout_ms: int,
        max_request_bytes: int,
        max_response_bytes: int,
    ) -> UpstreamResult:
        await self.policy.validate_before_connect(request.url)
        timeout_seconds = timeout_ms / 1000
        timeout = httpx.Timeout(
            connect=min(self.client.timeout.connect or timeout_seconds, timeout_seconds),
            read=min(self.client.timeout.read or timeout_seconds, timeout_seconds),
            write=min(self.client.timeout.write or timeout_seconds, timeout_seconds),
            pool=min(self.client.timeout.pool or timeout_seconds, timeout_seconds),
        )
        url = _append_query(request.url, request.query)
        if request.multipart_body is not None:
            files: list[tuple[str, tuple[object, ...]]] = []
            for part in request.multipart_body:
                value: tuple[object, ...]
                if part.filename is None:
                    value = (None, part.content)
                else:
                    value = (part.filename, part.content, part.content_type)
                files.append((part.name, value))
            outbound = self.client.build_request(
                request.method,
                url,
                headers=request.headers,
                files=files,  # pyright: ignore[reportArgumentType]
                timeout=timeout,
            )
        elif request.form_body is not None:
            outbound = self.client.build_request(
                request.method,
                url,
                headers=request.headers,
                content=urlencode(request.form_body).encode("utf-8"),
                timeout=timeout,
            )
        else:
            outbound = self.client.build_request(
                request.method,
                url,
                headers=request.headers,
                json=request.json_body,
                timeout=timeout,
            )
        content_length = outbound.headers.get("content-length")
        effective_request_limit = min(self.max_request_bytes, max_request_bytes)
        if content_length is not None and int(content_length) > effective_request_limit:
            raise UpstreamRequestTooLargeError()

        try:
            async with asyncio.timeout(timeout_seconds):
                try:
                    response = await self.client.send(outbound, stream=True)
                except httpx.TimeoutException as exc:
                    raise UpstreamTimeoutError() from exc
                except httpx.HTTPError as exc:
                    raise UpstreamConnectionError() from exc
                try:
                    body = await read_bounded_body(response, max_bytes=max_response_bytes)
                finally:
                    await response.aclose()
        except TimeoutError as exc:
            raise UpstreamTimeoutError() from exc

        content_type = (
            response.headers.get("content-type", "application/octet-stream")
            .split(";", 1)[0]
            .strip()
            .lower()
        )
        if response.status_code >= 300:
            return UpstreamResult(
                response.status_code,
                content_type,
                {"error": "upstream_http_error", "status": response.status_code},
            )
        if not body:
            data: object = None
        elif content_type == "application/json" or content_type.endswith("+json"):
            try:
                data = json.loads(body)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise UpstreamContentTypeError() from exc
        elif content_type.startswith("text/"):
            data = body.decode("utf-8", errors="replace")
        else:
            raise UpstreamContentTypeError()
        return UpstreamResult(response.status_code, content_type, data)

    async def close(self) -> None:
        await self.client.aclose()


def _append_query(url: str, parameters: tuple[QueryParameter, ...]) -> str:
    if not parameters:
        return url
    encoded: list[str] = []
    reserved_safe = ":/?@!$'()*+,;"
    for parameter in parameters:
        name = quote(parameter.name, safe="")
        safe = reserved_safe if parameter.allow_reserved else ""
        value = quote(parameter.value, safe=safe)
        encoded.append(f"{name}={value}")
    return f"{url}?{'&'.join(encoded)}"
