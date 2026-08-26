from collections.abc import Iterable

import pytest

from app.core.exceptions import SecurityPolicyError
from app.core.network_policy import UrlPolicy


def _resolver(addresses: Iterable[str]):
    async def resolve(_hostname: str, _port: int) -> Iterable[str]:
        return addresses

    return resolve


@pytest.mark.asyncio
async def test_url_policy_rejects_credentials_http_and_private_dns() -> None:
    policy = UrlPolicy(resolver=_resolver(["10.1.2.3"]))

    with pytest.raises(SecurityPolicyError, match="HTTPS"):
        await policy.validate("http://api.example.com/spec.json")
    with pytest.raises(SecurityPolicyError, match="credentials"):
        await policy.validate("https://user:pass@api.example.com/spec.json")
    with pytest.raises(SecurityPolicyError, match="blocked private"):
        await policy.validate("https://api.example.com/spec.json")


@pytest.mark.asyncio
async def test_url_policy_allows_public_dns_and_explicit_private_host() -> None:
    public = UrlPolicy(resolver=_resolver(["93.184.216.34"]))
    validated = await public.validate("https://EXAMPLE.com/spec.json#fragment")
    assert validated.url == "https://example.com/spec.json"

    private = UrlPolicy(
        allowed_private_hosts=["api.internal"],
        resolver=_resolver(["10.1.2.3"]),
    )
    assert (await private.validate("https://api.internal/openapi.yaml")).hostname == "api.internal"


@pytest.mark.asyncio
async def test_url_policy_revalidates_every_destination_independently() -> None:
    calls: list[str] = []

    async def resolver(hostname: str, _port: int) -> Iterable[str]:
        calls.append(hostname)
        return ["93.184.216.34"] if hostname == "public.example" else ["169.254.169.254"]

    policy = UrlPolicy(resolver=resolver)
    await policy.validate("https://public.example/spec")
    with pytest.raises(SecurityPolicyError):
        await policy.validate("https://metadata.example/latest")
    assert calls == ["public.example", "metadata.example"]
