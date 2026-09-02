import asyncio
from dataclasses import dataclass
from typing import cast

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


@dataclass(frozen=True, slots=True)
class _BodyRejected(Exception):
    status_code: int
    code: str
    message: str


class _SpoolBudget:
    def __init__(self, capacity_bytes: int) -> None:
        self._capacity_bytes = capacity_bytes
        self._reserved_bytes = 0
        self._lock = asyncio.Lock()

    async def reserve(self, amount: int) -> bool:
        async with self._lock:
            if amount > self._capacity_bytes - self._reserved_bytes:
                return False
            self._reserved_bytes += amount
            return True

    async def release(self, amount: int) -> None:
        async with self._lock:
            self._reserved_bytes = max(0, self._reserved_bytes - amount)


class MultipartSpoolLimitMiddleware:
    """Bound multipart request bytes before Starlette writes them into its spool."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        request_max_bytes: int,
        capacity_bytes: int,
    ) -> None:
        if request_max_bytes < 1 or capacity_bytes < request_max_bytes:
            raise ValueError("multipart request/spool limits are invalid")
        self._app = app
        self._request_max_bytes = request_max_bytes
        self._budget = _SpoolBudget(capacity_bytes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._is_multipart(scope):
            await self._app(scope, receive, send)
            return

        try:
            declared = self._content_length(scope)
        except _BodyRejected as exc:
            await self._reject(scope, receive, send, exc)
            return
        if declared is not None and declared > self._request_max_bytes:
            await self._reject(
                scope,
                receive,
                send,
                _BodyRejected(413, "PAYLOAD_TOO_LARGE", "Multipart request is too large"),
            )
            return

        reserved = declared or 0
        if reserved and not await self._budget.reserve(reserved):
            await self._reject(
                scope,
                receive,
                send,
                _BodyRejected(
                    503,
                    "UPLOAD_CAPACITY_EXHAUSTED",
                    "Multipart upload capacity is temporarily exhausted",
                ),
            )
            return

        consumed = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal consumed, reserved
            message = await receive()
            if message["type"] != "http.request":
                return message
            chunk = message.get("body", b"")
            consumed += len(chunk)
            if consumed > self._request_max_bytes:
                raise _BodyRejected(413, "PAYLOAD_TOO_LARGE", "Multipart request is too large")
            if consumed > reserved:
                additional = consumed - reserved
                if not await self._budget.reserve(additional):
                    raise _BodyRejected(
                        503,
                        "UPLOAD_CAPACITY_EXHAUSTED",
                        "Multipart upload capacity is temporarily exhausted",
                    )
                reserved += additional
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self._app(scope, limited_receive, tracked_send)
        except _BodyRejected as exc:
            if response_started:
                raise
            await self._reject(scope, receive, send, exc)
        finally:
            if reserved:
                await self._budget.release(reserved)

    @staticmethod
    def _is_multipart(scope: Scope) -> bool:
        for raw_name, raw_value in scope.get("headers", []):
            if raw_name.lower() == b"content-type":
                return raw_value.lower().startswith(b"multipart/form-data")
        return False

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        values = [
            raw_value
            for raw_name, raw_value in scope.get("headers", [])
            if raw_name.lower() == b"content-length"
        ]
        if not values:
            return None
        if len(set(values)) != 1:
            raise _BodyRejected(400, "INVALID_CONTENT_LENGTH", "Content-Length is invalid")
        try:
            value = int(values[0].decode("ascii"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise _BodyRejected(400, "INVALID_CONTENT_LENGTH", "Content-Length is invalid") from exc
        if value < 0:
            raise _BodyRejected(400, "INVALID_CONTENT_LENGTH", "Content-Length is invalid")
        return value

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
        rejection: _BodyRejected,
    ) -> None:
        state = scope.get("state")
        state_values = cast(dict[str, object], state) if isinstance(state, dict) else {}
        request_id_value = state_values.get("request_id")
        request_id = request_id_value if isinstance(request_id_value, str) else None
        headers = {"Retry-After": "1"} if rejection.status_code == 503 else None
        response = JSONResponse(
            status_code=rejection.status_code,
            content={
                "error": {
                    "code": rejection.code,
                    "message": rejection.message,
                    "details": {},
                    "request_id": request_id,
                }
            },
            headers=headers,
        )
        await response(scope, receive, send)
