import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from mcp_contracts import ServerDefinition

from app.executor.errors import DestinationPolicyError

AddressResolver = Callable[[str, int], Awaitable[Iterable[str]]]
_MAX_RESOLVED_ADDRESSES = 32


async def _system_resolver(hostname: str, port: int) -> Iterable[str]:
    loop = asyncio.get_running_loop()
    try:
        records = await loop.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise DestinationPolicyError("Upstream hostname resolution failed") from exc
    return {record[4][0].split("%", 1)[0] for record in records if isinstance(record[4][0], str)}


def _normalized_host(hostname: str) -> str:
    return hostname.rstrip(".").encode("idna").decode("ascii").lower()


def _effective_port(scheme: str, port: int | None) -> int:
    if port is not None:
        return port
    return 443 if scheme == "https" else 80


@dataclass(frozen=True, slots=True)
class AllowedOrigin:
    scheme: str
    hostname: str
    port: int
    base_path: str

    @classmethod
    def from_url(cls, value: str) -> "AllowedOrigin":
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("upstream URL must be absolute HTTP(S)")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("upstream URL contains forbidden components")
        try:
            port = _effective_port(parsed.scheme, parsed.port)
        except ValueError as exc:
            raise ValueError("upstream URL has an invalid port") from exc
        base_path = parsed.path.rstrip("/")
        decoded_path = unquote(base_path)
        if (
            "\\" in decoded_path
            or any(part in {".", ".."} for part in decoded_path.split("/"))
            or "%2f" in base_path.lower()
            or "%5c" in base_path.lower()
        ):
            raise ValueError("upstream base URL contains unsafe path segments")
        return cls(parsed.scheme, _normalized_host(parsed.hostname), port, base_path)

    @property
    def authority(self) -> str:
        default = (self.scheme == "https" and self.port == 443) or (
            self.scheme == "http" and self.port == 80
        )
        return self.hostname if default else f"{self.hostname}:{self.port}"

    def resolve(self, operation_path: str) -> str:
        if (
            not operation_path.startswith("/")
            or operation_path.startswith("//")
            or "\\" in operation_path
            or "?" in operation_path
            or "#" in operation_path
            or any(character in operation_path for character in "\r\n\x00")
            or any(segment in {".", ".."} for segment in operation_path.split("/"))
        ):
            raise DestinationPolicyError("Resolved upstream path is unsafe")
        path = f"{self.base_path}/{operation_path.lstrip('/')}"
        return urlunsplit((self.scheme, self.authority, path, "", ""))


class UpstreamUrlPolicy:
    def __init__(
        self,
        servers: list[ServerDefinition] | tuple[ServerDefinition, ...],
        *,
        allowed_private_hosts: list[str] | tuple[str, ...] = (),
        allowed_development_hosts: list[str] | tuple[str, ...] = (),
        development_mode: bool = False,
        resolver: AddressResolver = _system_resolver,
    ) -> None:
        self._origins = {server.id: AllowedOrigin.from_url(str(server.url)) for server in servers}
        if len(self._origins) != len(servers):
            raise ValueError("server identifiers must be unique")
        self._allowed_private_hosts = {_normalized_host(value) for value in allowed_private_hosts}
        self._allowed_development_hosts = {
            _normalized_host(value) for value in allowed_development_hosts
        }
        self._development_mode = development_mode
        self._resolver = resolver

    def resolve(self, server_ref: str, operation_path: str) -> str:
        try:
            origin = self._origins[server_ref]
        except KeyError as exc:
            raise DestinationPolicyError("Manifest references an unknown upstream server") from exc
        return origin.resolve(operation_path)

    def assert_url_is_allowlisted(self, url: str) -> AllowedOrigin:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise DestinationPolicyError()
        if parsed.username or parsed.password or parsed.fragment:
            raise DestinationPolicyError()
        try:
            origin = AllowedOrigin(
                parsed.scheme,
                _normalized_host(parsed.hostname),
                _effective_port(parsed.scheme, parsed.port),
                "",
            )
        except (UnicodeError, ValueError) as exc:
            raise DestinationPolicyError() from exc
        if not any(
            origin.scheme == allowed.scheme
            and origin.hostname == allowed.hostname
            and origin.port == allowed.port
            for allowed in self._origins.values()
        ):
            raise DestinationPolicyError()
        return origin

    async def validate_before_connect(self, url: str) -> None:
        origin = self.assert_url_is_allowlisted(url)
        await self._validate_resolved_origin(origin)

    async def validate_configured_destination(self, url: str) -> None:
        """Validate a non-caller-controlled auth/discovery URL against network policy."""
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise DestinationPolicyError()
        if parsed.username or parsed.password or parsed.fragment:
            raise DestinationPolicyError()
        if parsed.scheme != "https" and not self._development_mode:
            raise DestinationPolicyError("Configured authentication endpoints must use HTTPS")
        try:
            origin = AllowedOrigin(
                parsed.scheme,
                _normalized_host(parsed.hostname),
                _effective_port(parsed.scheme, parsed.port),
                "",
            )
        except (UnicodeError, ValueError) as exc:
            raise DestinationPolicyError() from exc
        await self._validate_resolved_origin(origin)

    async def _validate_resolved_origin(self, origin: AllowedOrigin) -> None:
        await self.resolve_for_connection(origin.hostname, origin.port)

    async def resolve_for_connection(self, hostname: str, port: int) -> tuple[str, ...]:
        """Resolve, validate, and return the exact addresses a socket may use."""

        try:
            normalized_hostname = _normalized_host(hostname)
        except UnicodeError as exc:
            raise DestinationPolicyError("Upstream hostname is invalid") from exc
        if not 1 <= port <= 65_535:
            raise DestinationPolicyError("Upstream port is invalid")
        addresses = await self._resolve(normalized_hostname, port)
        if not addresses:
            raise DestinationPolicyError("Upstream hostname did not resolve")
        if len(addresses) > _MAX_RESOLVED_ADDRESSES:
            raise DestinationPolicyError("Upstream hostname resolved to too many addresses")
        for address in addresses:
            if not self._address_is_allowed(normalized_hostname, address):
                raise DestinationPolicyError()
        return tuple(str(address) for address in addresses)

    async def _resolve(
        self, hostname: str, port: int
    ) -> tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]:
        try:
            literal = ipaddress.ip_address(hostname)
        except ValueError:
            try:
                raw_addresses = await self._resolver(hostname, port)
            except DestinationPolicyError:
                raise
            except OSError as exc:
                raise DestinationPolicyError("Upstream hostname resolution failed") from exc
            addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
            try:
                for raw_address in raw_addresses:
                    addresses.add(ipaddress.ip_address(raw_address.split("%", 1)[0]))
            except ValueError as exc:
                raise DestinationPolicyError("Upstream DNS returned an invalid address") from exc
            return tuple(sorted(addresses, key=lambda address: (address.version, int(address))))
        return (literal,)

    def _address_is_allowed(
        self,
        hostname: str,
        address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    ) -> bool:
        if address.is_global:
            return True
        development_allowed = (
            self._development_mode
            and hostname in self._allowed_development_hosts
            and not address.is_multicast
            and not address.is_unspecified
        )
        if address.is_private and not (
            address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            return hostname in self._allowed_private_hosts or development_allowed
        return development_allowed


def encode_path_value(value: object) -> str:
    text = str(value)
    if text in {".", ".."} or any(character in text for character in "\r\n\x00"):
        raise DestinationPolicyError("Path parameter contains an unsafe value")
    return quote(text, safe="")
