from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MCP_LICA_",
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_origin: str = "http://localhost:8080"

    database_url: str = "postgresql+asyncpg://mcplica:mcplica@localhost:5432/mcplica"
    redis_url: str = "redis://localhost:6379/0"
    rq_queue: str = "mcplica"

    milvus_uri: str = "http://localhost:19530"
    milvus_token: str | None = None
    milvus_collection: str = "mcplica_document_chunks"

    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str | None = None
    openrouter_site_url: str | None = None
    openrouter_app_name: str = "MCPlica"

    secret_encryption_key: str | None = Field(default=None, repr=False)
    artifact_root: str = "./artifacts"

    docker_base_url: str = "unix:///var/run/docker.sock"
    mcp_runtime_image: str = "mcplica/mcp-runtime:dev"
    mcp_domain: str = "mcp.localhost"
    traefik_network: str = "mcplica-edge"

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
