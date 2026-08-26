import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from app.core.exceptions import SecurityPolicyError, ValidationError

AddressResolver = Callable[[str, int], Awaitable[Iterable[str]]]


async def resolve_addresses(hostname: str, port: int) -> list[str]:
    def _resolve() -> list[str]:
        results = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        return sorted({str(item[4][0]) for item in results})

    try:
        return await asyncio.to_thread(_resolve)
    except OSError as exc:
        raise SecurityPolicyError("Source hostname could not be resolved") from exc


@dataclass(frozen=True, slots=True)
class ValidatedUrl:
    url: str
    hostname: str
    port: int
    resolved_addresses: tuple[str, ...]


class UrlPolicy:
    def __init__(
        self,
        *,
        allow_http: bool = False,
        allowed_private_hosts: Iterable[str] = (),
        allowed_private_cidrs: Iterable[str] = (),
        allow_special_use: bool = False,
        resolver: AddressResolver = resolve_addresses,
    ) -> None:
        self._allow_http = allow_http
        self._allowed_hosts = frozenset(self._normalize_hostname(v) for v in allowed_private_hosts)
        try:
            self._allowed_networks = tuple(
                ipaddress.ip_network(value, strict=True) for value in allowed_private_cidrs
            )
        except ValueError as exc:
            raise ValueError("Invalid source private-network allowlist CIDR") from exc
        self._resolver = resolver
        self._allow_special_use = allow_special_use

    @staticmethod
    def _normalize_hostname(value: str) -> str:
        hostname = value.strip().rstrip(".").casefold()
        if not hostname:
            raise ValueError("hostname cannot be empty")
        try:
            return hostname.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("hostname is not valid IDNA") from exc

    def validate_syntax(self, url: str) -> tuple[str, str, int]:
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError as exc:
            raise ValidationError("Source URL is malformed") from exc
        allowed_schemes = {"https", "http"} if self._allow_http else {"https"}
        if parsed.scheme.casefold() not in allowed_schemes:
            raise SecurityPolicyError("Source URL must use HTTPS")
        if parsed.username is not None or parsed.password is not None:
            raise SecurityPolicyError("Source URL must not contain credentials")
        if not parsed.hostname:
            raise ValidationError("Source URL must contain a hostname")
        hostname = self._normalize_hostname(parsed.hostname)
        effective_port = port or (443 if parsed.scheme.casefold() == "https" else 80)
        if effective_port < 1 or effective_port > 65535:
            raise ValidationError("Source URL port is invalid")
        normalized_netloc = hostname
        if ":" in hostname and not hostname.startswith("["):
            normalized_netloc = f"[{hostname}]"
        if port is not None:
            normalized_netloc = f"{normalized_netloc}:{port}"
        normalized = urlunsplit(
            (
                parsed.scheme.casefold(),
                normalized_netloc,
                parsed.path or "/",
                parsed.query,
                "",
            )
        )
        return normalized, hostname, effective_port

    def _host_explicitly_allowed(self, hostname: str) -> bool:
        for allowed in self._allowed_hosts:
            if allowed.startswith("*."):
                suffix = allowed[1:]
                if hostname.endswith(suffix) and hostname != suffix[1:]:
                    return True
            elif hostname == allowed:
                return True
        return False

    def _address_allowed(self, hostname: str, raw_address: str) -> bool:
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as exc:
            raise SecurityPolicyError("Source DNS returned an invalid address") from exc
        if address.is_global:
            return True
        if (
            address.is_link_local
            or address.is_loopback
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            return self._allow_special_use and self._host_explicitly_allowed(hostname)
        if self._host_explicitly_allowed(hostname):
            return True
        return any(address in network for network in self._allowed_networks)

    async def validate(self, url: str) -> ValidatedUrl:
        normalized, hostname, port = self.validate_syntax(url)
        try:
            literal_address = ipaddress.ip_address(hostname)
        except ValueError:
            addresses = tuple(await self._resolver(hostname, port))
        else:
            addresses = (str(literal_address),)
        if not addresses:
            raise SecurityPolicyError("Source hostname resolved to no addresses")
        blocked = [value for value in addresses if not self._address_allowed(hostname, value)]
        if blocked:
            raise SecurityPolicyError(
                "Source destination resolves to a blocked private or special-use address"
            )
        return ValidatedUrl(normalized, hostname, port, addresses)
