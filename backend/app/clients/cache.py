from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.clients.base import AsyncClient
from app.core.exceptions import ClientUnavailableError


class RedisClient(AsyncClient):
    def __init__(self, url: str) -> None:
        self.redis = Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
            url,
            decode_responses=True,
        )

    async def health(self) -> bool:
        try:
            result = await self.redis.ping()  # pyright: ignore[reportUnknownMemberType]
            return bool(result)
        except Exception:
            return False

    async def get(self, key: str) -> str | None:
        try:
            return await self.redis.get(key)
        except RedisError as exc:
            raise ClientUnavailableError("Redis cache read failed") from exc

    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None:
        try:
            await self.redis.set(key, value, ex=ttl_seconds)
        except RedisError as exc:
            raise ClientUnavailableError("Redis cache write failed") from exc

    async def delete(self, key: str) -> None:
        try:
            await self.redis.delete(key)
        except RedisError as exc:
            raise ClientUnavailableError("Redis cache delete failed") from exc

    async def publish(self, channel: str, value: str) -> int:
        try:
            result = await self.redis.publish(  # pyright: ignore[reportUnknownMemberType]
                channel,
                value,
            )
            return int(cast(int, result))
        except RedisError as exc:
            raise ClientUnavailableError("Redis publish failed") from exc

    async def rate_limit_exceeded(self, key: str, *, limit: int, window_seconds: int) -> bool:
        script = """
        local count = redis.call('INCR', KEYS[1])
        if count == 1 then
            redis.call('EXPIRE', KEYS[1], ARGV[1])
        end
        return count
        """
        try:
            result = await cast(
                Awaitable[object],
                self.redis.eval(
                    script,
                    1,  # pyright: ignore[reportArgumentType]
                    key,
                    str(window_seconds),
                ),
            )
            return int(cast(int | str, result)) > limit
        except RedisError as exc:
            raise ClientUnavailableError("Redis rate-limit check failed") from exc

    async def close(self) -> None:
        await self.redis.aclose()
