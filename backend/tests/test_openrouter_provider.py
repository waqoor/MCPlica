import gzip

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from app.clients.ai import OpenRouterClient
from app.clients.http import HttpClient
from app.core.exceptions import AIAnalysisError, ClientResponseError
from app.providers.ai.openrouter import OpenRouterProvider


class _Enrichment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str


async def _key() -> str:
    return "test-key"


@pytest.mark.parametrize(
    ("site_url", "expected_referer"),
    [
        (None, None),
        ("https://mcplica.example", "https://mcplica.example"),
    ],
)
async def test_base_url_routes_requests_while_site_url_controls_attribution(
    site_url: str | None,
    expected_referer: str | None,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "gateway.example"
        assert request.url.path == "/api/v1/models"
        assert request.headers.get("HTTP-Referer") == expected_referer
        assert request.headers["X-Title"] == "MCPlica test"
        return httpx.Response(200, json={"data": []})

    http = HttpClient(transport=httpx.MockTransport(handler))
    client = OpenRouterClient(
        http,
        _key,
        "https://gateway.example/api/v1/",
        site_url=site_url,
        app_name="MCPlica test",
    )
    assert await client.models() == []
    await http.close()


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
    assert result.cost is not None
    assert result.cost["cost"] == pytest.approx(0.001)
    assert result.cost["accounting_status"] == "complete"
    assert result.usage is not None
    assert result.usage["total_tokens"] == 12
    assert result.usage["accounting_status"] == "complete"
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


async def test_model_catalog_requests_all_output_modalities() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models")
        assert dict(request.url.params) == {"output_modalities": "all"}
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "text/model",
                        "name": "Text",
                        "architecture": {"output_modalities": ["text"]},
                    },
                    {
                        "id": "embedding/model",
                        "name": "Embedding",
                        "architecture": {"output_modalities": ["embeddings"]},
                    },
                ]
            },
        )

    http = HttpClient(transport=httpx.MockTransport(handler))
    provider = OpenRouterProvider(OpenRouterClient(http, _key, "https://openrouter.example/api/v1"))
    models = await provider.list_models()
    await http.close()

    assert [model.id for model in models] == ["text/model", "embedding/model"]
    assert models[1].output_modalities == frozenset({"embeddings"})


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Content-Length": "1"},
        {"Content-Encoding": "gzip"},
    ],
    ids=["absent-length", "understated-length", "compressed"],
)
async def test_model_catalog_response_is_bounded_before_json_parsing(
    headers: dict[str, str],
) -> None:
    decoded = b'{"data":[' + (b" " * 128) + b"]}"
    content = gzip.compress(decoded) if headers.get("Content-Encoding") == "gzip" else decoded
    http = HttpClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=content, headers=headers)
        )
    )
    provider = OpenRouterProvider(
        OpenRouterClient(
            http,
            _key,
            "https://openrouter.example/api/v1",
            catalog_max_response_bytes=32,
        )
    )
    with pytest.raises(ClientResponseError, match="byte limit"):
        await provider.list_models()
    await http.close()


@pytest.mark.parametrize(
    "data",
    [
        [
            {"index": 0, "embedding": [0.1, 0.2]},
            {"index": 0, "embedding": [0.3, 0.4]},
        ],
        [
            {"index": -1, "embedding": [0.1, 0.2]},
            {"index": 1, "embedding": [0.3, 0.4]},
        ],
        [
            {"index": 0, "embedding": [0.1, 0.2]},
            {"index": 2, "embedding": [0.3, 0.4]},
        ],
        [
            {"index": 0, "embedding": [0.1, 0.2]},
            {"embedding": [0.3, 0.4]},
        ],
        [
            {"index": 0, "embedding": [0.1, 0.2]},
            {"index": 1, "embedding": [0.3]},
        ],
    ],
    ids=["duplicate", "negative", "out-of-range", "missing", "mixed-dimension"],
)
async def test_embeddings_reject_malformed_index_contract(
    data: list[dict[str, object]],
) -> None:
    http = HttpClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"model": "embed/model", "data": data},
            )
        )
    )
    provider = OpenRouterProvider(OpenRouterClient(http, _key, "https://openrouter.example/api/v1"))
    with pytest.raises(ClientResponseError):
        await provider.embed(model="embed/model", texts=["one", "two"])
    await http.close()


async def test_structured_generation_has_a_separate_bounded_schema_retry_budget() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = '{"unexpected":true}' if calls == 1 else '{"title":"Recovered"}'
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {
                    "total_tokens": 5 if calls == 1 else 10,
                    "cost": 0.002 if calls == 1 else 0.003,
                },
            },
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
    assert result.usage is not None
    assert result.usage["total_tokens"] == 15
    assert result.usage["accounting_status"] == "complete"
    assert [attempt["outcome"] for attempt in result.usage["attempts"]] == [
        "rejected",
        "accepted",
    ]
    assert result.cost is not None
    assert result.cost["cost"] == pytest.approx(0.005)
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
    with pytest.raises(AIAnalysisError, match="bounded retries") as failure:
        await failing.structured_generate(
            model="example/model",
            messages=[{"role": "user", "content": "facts"}],
            response_model=_Enrichment,
            schema_name="operation_enrichment",
        )
    assert failure.value.usage["accounting_status"] == "unavailable"
    assert failure.value.usage["attempts"][0]["outcome"] == "rejected"
    await failing_http.close()
