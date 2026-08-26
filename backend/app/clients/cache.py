from redis.asyncio import Redis

from app.clients.base import AsyncClient


class RedisClient(AsyncClient):
    def __init__(self, url: str) -> None:
        self.redis = Redis.from_url(url, decode_responses=True)

    async def health(self) -> bool:
        try:
            return bool(await self.redis.ping())
        except Exception:
            return False

    async def get(self, key: str) -> str | None:
        return await self.redis.get(key)

    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None:
        await self.redis.set(key, value, ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

    async def close(self) -> None:
        await self.redis.aclose()
