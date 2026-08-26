from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_", extra="ignore")

    manifest_path: str = "/runtime/manifest.json"
    runtime_host: str = "0.0.0.0"
    runtime_port: int = 8000
    allowed_hosts: str = "localhost,localhost:*,127.0.0.1,127.0.0.1:*"
    allowed_origins: str = ""
    inbound_bearer_token: str | None = None

    @property
    def allowed_host_list(self) -> list[str]:
        return [part.strip() for part in self.allowed_hosts.split(",") if part.strip()]

    @property
    def allowed_origin_list(self) -> list[str]:
        return [part.strip() for part in self.allowed_origins.split(",") if part.strip()]


@lru_cache
def get_settings() -> RuntimeSettings:
    return RuntimeSettings()
