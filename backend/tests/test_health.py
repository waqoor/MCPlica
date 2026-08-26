import pytest

from app.api.health import health


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    assert await health() == {"status": "ok", "service": "mcplica-api"}
