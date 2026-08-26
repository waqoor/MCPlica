from collections.abc import Mapping, Sequence
from typing import Any, Final, cast

REDACTED: Final = "[REDACTED]"
SENSITIVE_KEYS: Final = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "client_secret",
        "cookie",
        "password",
        "refresh_token",
        "secret",
        "set-cookie",
        "token",
    }
)


def is_sensitive_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEYS)


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {
            str(key): REDACTED if is_sensitive_key(str(key)) else redact(item)
            for key, item in mapping.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact(item) for item in cast(Sequence[object], value)]
    return value
