import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from app.clients.ai import OpenRouterClient
from app.clients.http import HttpClient
from app.core.exceptions import AIAnalysisError
from app.providers.ai.openrouter import OpenRouterProvider


class _Enrichment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str


async def _key() -> str:
    return "test-key"


async def test_structured_generation_retries_transport_rate_limit_and_validates() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.extensions["timeout"]["read"] == 17.0
        if calls == 1:
            return httpx.Response(429, json={"error": "slow down"})
        return httpx.Response(
            200,
            json={
                "model": "example/model",
                "choices": [{"message": {"content": '{"title":"Get product"}'}}],
                "usage": {"total_tokens": 12, "cost": 0.001},
            },
        )

    delays: list[float] = []

    async def no_sleep(delay: float) -> None:
        delays.append(delay)

    http = HttpClient(transport=httpx.MockTransport(handler))
    client = OpenRouterClient(
        http,
        _key,
        "https://openrouter.example/api/v1",
        max_attempts=2,
        timeout_seconds=17.0,
        sleep=no_sleep,
    )
    provider = OpenRouterProvider(client)
    result = await provider.structured_generate(
        model="example/model",
        messages=[{"role": "user", "content": "facts"}],
        response_model=_Enrichment,
        schema_name="operation_enrichment",
    )
    assert result.value.title == "Get product"
    assert result.cost == {"cost": 0.001}
    assert calls == 2
    assert len(delays) == 1
    await http.close()


async def test_embeddings_preserve_provider_index_order_and_dimensions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/embeddings")
        return httpx.Response(
            200,
            json={
                "model": "embed/model",
                "data": [
                    {"index": 1, "embedding": [0.3, 0.4]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ],
                "usage": {"total_tokens": 4},
            },
        )

    http = HttpClient(transport=httpx.MockTransport(handler))
    provider = OpenRouterProvider(OpenRouterClient(http, _key, "https://openrouter.example/api/v1"))
    result = await provider.embed(model="embed/model", texts=["one", "two"])
    assert result.vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert result.dimensions == 2
    await http.close()


async def test_structured_generation_has_a_separate_bounded_schema_retry_budget() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = '{"unexpected":true}' if calls == 1 else '{"title":"Recovered"}'
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    http = HttpClient(transport=httpx.MockTransport(handler))
    provider = OpenRouterProvider(
        OpenRouterClient(http, _key, "https://openrouter.example/api/v1", max_attempts=1),
        structured_attempts=2,
    )
    result = await provider.structured_generate(
        model="example/model",
        messages=[{"role": "user", "content": "facts"}],
        response_model=_Enrichment,
        schema_name="operation_enrichment",
    )
    assert result.value.title == "Recovered"
    assert calls == 2
    await http.close()

    failing_http = HttpClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"choices": [{"message": {"content": '{"unexpected":true}'}}]},
            )
        )
    )
    failing = OpenRouterProvider(
        OpenRouterClient(
            failing_http,
            _key,
            "https://openrouter.example/api/v1",
            max_attempts=1,
        ),
        structured_attempts=1,
    )
    with pytest.raises(AIAnalysisError, match="bounded retries"):
        await failing.structured_generate(
            model="example/model",
            messages=[{"role": "user", "content": "facts"}],
            response_model=_Enrichment,
            schema_name="operation_enrichment",
        )
    await failing_http.close()
