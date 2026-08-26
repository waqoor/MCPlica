import httpx

from app.executor.errors import (
    UpstreamConnectionError,
    UpstreamResponseTooLargeError,
    UpstreamTimeoutError,
)


async def read_bounded_body(response: httpx.Response, *, max_bytes: int) -> bytes:
    declared = response.headers.get("content-length")
    if declared is not None:
        try:
            declared_bytes = int(declared)
        except ValueError as exc:
            raise UpstreamConnectionError() from exc
        if declared_bytes < 0:
            raise UpstreamConnectionError()
        if declared_bytes > max_bytes:
            raise UpstreamResponseTooLargeError()

    chunks: list[bytes] = []
    received = 0
    try:
        async for chunk in response.aiter_bytes():
            received += len(chunk)
            if received > max_bytes:
                raise UpstreamResponseTooLargeError()
            chunks.append(chunk)
    except httpx.TimeoutException as exc:
        raise UpstreamTimeoutError() from exc
    except httpx.HTTPError as exc:
        raise UpstreamConnectionError() from exc
    return b"".join(chunks)
