from functools import lru_cache
from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated, Literal

from pydantic import (
    AnyHttpUrl,
    BeforeValidator,
    Field,
    SecretStr,
    TypeAdapter,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.hostname import normalize_dns_hostname


def _split_csv(value: object) -> object:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


def _empty_secret_to_none(value: object) -> object:
    return None if value == "" else value


CsvList = Annotated[list[str], NoDecode, BeforeValidator(_split_csv)]
OptionalSecret = Annotated[SecretStr | None, BeforeValidator(_empty_secret_to_none)]
_HTTP_URL = TypeAdapter(AnyHttpUrl)


def _absolute_runtime_path(value: str) -> bool:
    return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _runtime_path_is_root(value: str) -> bool:
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return (posix.is_absolute() and len(posix.parts) == 1) or (
        windows.is_absolute() and len(windows.parts) == 1
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_domain: str = "api.localhost"
    frontend_origin: str = "http://localhost:8080"
    metrics_bearer_token: OptionalSecret = Field(default=None, repr=False)

    database_url: str = "postgresql+psycopg://mcplica:mcplica@localhost:5432/mcplica"
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=200)
    database_pool_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    readiness_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    redis_url: str = "redis://localhost:6379/0"
    build_queue_name: str = "mcplica-builds"
    deployment_queue_name: str = "mcplica-deployments"
    build_job_timeout_seconds: int = Field(default=3600, ge=60, le=86_400)
    build_job_max_attempts: int = Field(default=3, ge=1, le=8)
    build_concurrency: int = Field(default=2, ge=1, le=32)
    builders_can_deploy: bool = False
    source_retention_days: int | None = Field(default=None, ge=1, le=3650)
    build_retention_count: int | None = Field(default=20, ge=1, le=10_000)
    max_operations_per_project: int = Field(default=1_000, ge=1, le=100_000)
    deployment_job_timeout_seconds: int = Field(default=900, ge=60, le=7_200)
    deployment_job_max_attempts: int = Field(default=3, ge=1, le=8)

    milvus_uri: str = "http://localhost:19530"
    milvus_token: str | None = None
    milvus_collection: str = "mcplica_document_chunks"

    openrouter_api_key: OptionalSecret = Field(default=None, repr=False)
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_analysis_model: str | None = None
    openrouter_validation_model: str | None = None
    openrouter_embedding_model: str | None = None
    openrouter_site_url: str | None = None
    openrouter_app_name: str = "MCPlica"
    openrouter_timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    openrouter_max_attempts: int = Field(default=3, ge=1, le=8)
    openrouter_structured_max_attempts: int = Field(default=2, ge=1, le=5)
    openrouter_max_concurrency: int = Field(default=4, ge=1, le=32)
    openrouter_max_context_chars: int = Field(default=120_000, ge=1_000, le=1_000_000)
    semantic_retrieval_top_k: int = Field(default=5, ge=1, le=50)

    secret_encryption_key: OptionalSecret = Field(default=None, repr=False)
    secret_encryption_key_version: str = Field(default="v1", min_length=1, max_length=64)
    auth_signing_key: OptionalSecret = Field(default=None, repr=False)
    refresh_token_pepper: OptionalSecret = Field(default=None, repr=False)
    bootstrap_secret: OptionalSecret = Field(default=None, repr=False)
    access_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    refresh_token_ttl_seconds: int = Field(default=2_592_000, ge=3600, le=7_776_000)
    auth_cookie_name: str = "mcplica_access"
    refresh_cookie_name: str = "mcplica_refresh"
    csrf_cookie_name: str = "mcplica_csrf"
    login_rate_limit_attempts: int = Field(default=10, ge=1, le=100)
    login_rate_limit_window_seconds: int = Field(default=300, ge=10, le=3600)

    artifact_root: str = "./artifacts"
    upload_max_bytes: int = Field(default=100_000_000, ge=1_024, le=500_000_000)
    document_max_bytes: int = Field(default=100_000_000, ge=1_024, le=500_000_000)
    fetch_max_bytes: int = Field(default=25_000_000, ge=1_024, le=500_000_000)
    fetch_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    fetch_max_redirects: int = Field(default=3, ge=0, le=10)
    fetch_max_attempts: int = Field(default=3, ge=1, le=8)
    allow_http_source_urls: bool = False
    source_allowed_hosts: CsvList = Field(default_factory=list)
    source_allowed_private_cidrs: CsvList = Field(default_factory=list)
    documentation_chunk_chars: int = Field(default=6_000, ge=500, le=50_000)
    documentation_chunk_overlap_chars: int = Field(default=500, ge=0, le=5_000)
    documentation_max_chunks_per_project: int = Field(default=10_000, ge=1, le=100_000)
    document_parse_max_concurrency: int = Field(default=4, ge=1, le=32)
    pdf_max_pages: int = Field(default=500, ge=1, le=5_000)
    document_max_text_chars: int = Field(default=5_000_000, ge=1_000, le=50_000_000)
    embedding_batch_size: int = Field(default=64, ge=1, le=512)
    build_artifact_max_bytes: int = Field(
        default=100_000_000,
        ge=1_024,
        le=1_000_000_000,
    )
    runtime_upstream_timeout_ms: int = Field(default=30_000, ge=100, le=300_000)
    runtime_max_request_bytes: int = Field(
        default=10_000_000,
        ge=1_024,
        le=100_000_000,
    )
    runtime_max_response_bytes: int = Field(
        default=2_000_000,
        ge=1_024,
        le=50_000_000,
    )
    runtime_manifest_max_bytes: int = Field(default=10_000_000, ge=1_024, le=50_000_000)
    runtime_secret_bundle_max_bytes: int = Field(
        default=1_000_000,
        ge=1_024,
        le=10_000_000,
    )

    docker_base_url: str = "unix:///var/run/docker.sock"
    mcp_runtime_image: str = "mcplica/mcp-runtime:1.0.0"
    mcp_runtime_version: str = Field(default="1.0.0", min_length=1, max_length=64)
    mcp_runtime_pull_policy: Literal["never", "missing", "always"] = "missing"
    mcp_domain: str = "mcp.localhost"
    traefik_network: str = "mcplica-edge"
    traefik_container_name: str = "mcplica-traefik-1"
    traefik_entrypoint: str = "web"
    traefik_tls: bool = False
    traefik_cert_resolver: str | None = None
    runtime_host_root: str = "/var/lib/mcplica/runtime"
    runtime_worker_root: str = "/runtime-host"
    runtime_uid: int = Field(default=10_001, ge=1, le=2_147_483_647)
    runtime_gid: int = Field(default=10_001, ge=1, le=2_147_483_647)
    runtime_memory_bytes: int = Field(default=536_870_912, ge=67_108_864)
    runtime_nano_cpus: int = Field(default=1_000_000_000, ge=10_000_000, le=64_000_000_000)
    runtime_pids_limit: int = Field(default=256, ge=16, le=65_536)
    runtime_tmpfs_bytes: int = Field(default=67_108_864, ge=1_048_576, le=1_073_741_824)
    runtime_stop_timeout_seconds: int = Field(default=15, ge=1, le=300)
    runtime_health_timeout_seconds: float = Field(default=90.0, gt=0, le=900)
    runtime_health_poll_seconds: float = Field(default=1.0, ge=0.1, le=30)
    runtime_allowed_private_hosts: CsvList = Field(default_factory=list)
    runtime_allowed_development_hosts: CsvList = Field(default_factory=list)

    @field_validator("api_domain", "mcp_domain")
    @classmethod
    def validate_service_domain(cls, value: str) -> str:
        try:
            return normalize_dns_hostname(value)
        except ValueError as exc:
            raise ValueError("service domains must be DNS hostnames") from exc

    @field_validator("frontend_origin")
    @classmethod
    def validate_frontend_origin(cls, value: str) -> str:
        url = _HTTP_URL.validate_python(value)
        if url.path not in {None, "", "/"} or url.query is not None or url.fragment is not None:
            raise ValueError("frontend_origin must be an origin without a path, query, or fragment")
        return str(url).rstrip("/")

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def secure_cookies(self) -> bool:
        return self.is_production

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.build_queue_name == self.deployment_queue_name:
            raise ValueError("build and deployment jobs require separate RQ queues")
        for label, value in (
            ("build_queue_name", self.build_queue_name),
            ("deployment_queue_name", self.deployment_queue_name),
        ):
            if (
                not value.strip()
                or len(value) > 128
                or any(character in value for character in "\r\n\x00")
            ):
                raise ValueError(f"{label} is invalid")
        if not _absolute_runtime_path(self.runtime_host_root):
            raise ValueError("runtime_host_root must be an absolute Docker host path")
        if not _absolute_runtime_path(self.runtime_worker_root):
            raise ValueError("runtime_worker_root must be an absolute worker path")
        if _runtime_path_is_root(self.runtime_host_root) or _runtime_path_is_root(
            self.runtime_worker_root
        ):
            raise ValueError("runtime file roots cannot be filesystem roots")
        if self.is_production:
            missing = [
                name
                for name in (
                    "secret_encryption_key",
                    "auth_signing_key",
                    "refresh_token_pepper",
                )
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(
                    "production requires explicit secret configuration: " + ", ".join(missing)
                )
            if self.mcp_domain.endswith(".localhost"):
                raise ValueError("production requires an explicit non-localhost MCP domain")
            if not self.traefik_tls:
                raise ValueError("production requires TLS for generated MCP routes")
            image_name, separator, digest = self.mcp_runtime_image.rpartition("@sha256:")
            if (
                not separator
                or not image_name
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest.lower())
            ):
                raise ValueError("production requires a digest-pinned MCP runtime image")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
