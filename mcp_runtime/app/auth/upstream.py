import base64
import os
from dataclasses import dataclass, field

from mcp_contracts import AuthProfile


@dataclass
class AuthInjection:
    headers: dict[str, str] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)


def _required_env(name: str | None) -> str:
    if not name:
        raise RuntimeError("Auth profile does not define required environment variable")
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"Required runtime secret {name} is not configured")
    return value


def build_auth(profile: AuthProfile | None) -> AuthInjection:
    if profile is None or profile.type == "none":
        return AuthInjection()
    if profile.type == "bearer":
        token = _required_env(profile.secret_env)
        return AuthInjection(headers={"Authorization": f"Bearer {token}"})
    if profile.type == "api_key":
        secret = _required_env(profile.secret_env)
        if not profile.name or not profile.location:
            raise RuntimeError("API-key auth profile is incomplete")
        if profile.location == "header":
            return AuthInjection(headers={profile.name: f"{profile.prefix or ''}{secret}"})
        return AuthInjection(query={profile.name: f"{profile.prefix or ''}{secret}"})
    if profile.type == "basic":
        username = _required_env(profile.username_env)
        password = _required_env(profile.password_env)
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        return AuthInjection(headers={"Authorization": f"Basic {token}"})
    raise RuntimeError(f"Unsupported auth profile type {profile.type}")
