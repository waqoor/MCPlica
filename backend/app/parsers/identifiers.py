import hashlib
import re

_NON_IDENTIFIER = re.compile(r"[^a-zA-Z0-9_]+")
_ACRONYM_BOUNDARY = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CAMEL_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")
_MULTIPLE_UNDERSCORES = re.compile(r"_+")


def stable_digest(*parts: str, length: int = 16) -> str:
    payload = "\x1f".join(parts).encode()
    return hashlib.sha256(payload).hexdigest()[:length]


def normalize_identifier(value: str, *, max_length: int = 96) -> str:
    normalized = _ACRONYM_BOUNDARY.sub(r"\1_\2", value)
    normalized = _CAMEL_BOUNDARY.sub(r"\1_\2", normalized)
    normalized = _NON_IDENTIFIER.sub("_", normalized).strip("_").lower()
    normalized = _MULTIPLE_UNDERSCORES.sub("_", normalized)
    if not normalized:
        normalized = "operation"
    if normalized[0].isdigit():
        normalized = f"op_{normalized}"
    return normalized[:max_length]


def operation_key(method: str, path: str, operation_id: str | None) -> str:
    identity = operation_id.strip() if operation_id else f"{method.upper()} {path}"
    return f"op_{stable_digest(identity, length=24)}"


def tool_name_seed(method: str, path: str, operation_id: str | None) -> str:
    if operation_id:
        return normalize_identifier(operation_id)
    path_words = re.sub(r"[{}]", "", path).strip("/").replace("/", "_")
    return normalize_identifier(f"{method}_{path_words}")


def server_key(url: str, declared_id: str | None = None) -> str:
    if declared_id:
        return f"server_{normalize_identifier(declared_id, max_length=80)}"
    return f"server_{stable_digest(url, length=16)}"


def schema_key(name: str) -> str:
    return f"schema_{normalize_identifier(name, max_length=80)}_{stable_digest(name, length=8)}"


def pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")
