from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_", extra="ignore")

    environment: Literal["development", "test", "production"] = "production"
    runtime_version: str = "1.0.0"
    deployment_id: UUID | None = None
    manifest_path: str = "/runtime/manifest.json"
    manifest_sha256: str | None = None
    secret_bundle_path: str = "/run/secrets/mcplica-runtime.json"
    auth_overlay_sha256: str | None = None
    runtime_host: str = "0.0.0.0"
    runtime_port: int = Field(default=8000, ge=1, le=65535)
    public_base_url: str = "https://localhost"
    allowed_hosts: str = "localhost,localhost:*,127.0.0.1,127.0.0.1:*"
    allowed_origins: str = ""
    max_manifest_bytes: int = Field(default=10_000_000, ge=1_024, le=50_000_000)
    max_secret_bundle_bytes: int = Field(default=1_000_000, ge=1_024, le=10_000_000)
    max_mcp_request_bytes: int = Field(default=2_000_000, ge=1_024, le=50_000_000)
    max_upstream_request_bytes: int = Field(default=10_000_000, ge=1_024, le=50_000_000)
    http_max_connections: int = Field(default=100, ge=1, le=10_000)
    http_max_keepalive_connections: int = Field(default=20, ge=0, le=10_000)
    http_keepalive_expiry_seconds: float = Field(default=30.0, ge=1.0, le=300.0)
    http_connect_timeout_seconds: float = Field(default=10.0, gt=0.0, le=120.0)
    http_read_timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0)
    http_write_timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0)
    http_pool_timeout_seconds: float = Field(default=10.0, gt=0.0, le=120.0)
    tls_verify: bool = True
    trust_environment_proxy: bool = False
    require_secure_secret_permissions: bool = True
    log_level: str = "INFO"

    @model_validator(mode="after")
    def production_security_invariants(self) -> "RuntimeSettings":
        if self.http_max_keepalive_connections > self.http_max_connections:
            raise ValueError("keep-alive connection limit cannot exceed total connection limit")
        if self.environment == "production" and not self.tls_verify:
            raise ValueError("TLS verification cannot be disabled in production")
        if self.trust_environment_proxy:
            raise ValueError("runtime HTTP clients cannot inherit environment proxies")
        if self.environment == "production" and not self.require_secure_secret_permissions:
            raise ValueError("secure secret-file permissions are required in production")
        if self.environment == "production":
            for label, digest in (
                ("manifest", self.manifest_sha256),
                ("deployment authentication overlay", self.auth_overlay_sha256),
            ):
                if (
                    digest is None
                    or len(digest.removeprefix("sha256:")) != 64
                    or any(
                        character not in "0123456789abcdef"
                        for character in digest.removeprefix("sha256:").lower()
                    )
                ):
                    raise ValueError(f"production requires an expected {label} SHA-256")
        public_url = urlsplit(self.public_base_url)
        if (
            public_url.scheme not in {"http", "https"}
            or not public_url.hostname
            or public_url.username
            or public_url.password
            or public_url.query
            or public_url.fragment
            or public_url.path not in {"", "/"}
        ):
            raise ValueError("public_base_url must be an HTTP(S) origin without credentials")
        if self.environment == "production" and public_url.scheme != "https":
            raise ValueError("public_base_url must use HTTPS in production")
        self.public_base_url = self.public_base_url.rstrip("/")
        if not self.allowed_host_list or public_url.netloc.casefold() not in {
            value.casefold() for value in self.allowed_host_list
        }:
            raise ValueError("allowed_hosts must include the public MCP authority")
        if self.environment == "production" and any(
            "*" in value for value in self.allowed_host_list
        ):
            raise ValueError("production allowed_hosts cannot contain wildcards")
        for origin in self.allowed_origin_list:
            parsed_origin = urlsplit(origin)
            if (
                parsed_origin.scheme not in {"http", "https"}
                or not parsed_origin.hostname
                or parsed_origin.username
                or parsed_origin.password
                or parsed_origin.path not in {"", "/"}
                or parsed_origin.query
                or parsed_origin.fragment
            ):
                raise ValueError("allowed_origins must contain HTTP(S) origins only")
        if (
            self.environment == "production"
            and self.public_base_url not in self.allowed_origin_list
        ):
            raise ValueError("production allowed_origins must include public_base_url")
        if self.environment == "production" and (
            not self.manifest_path.startswith("/")
            or not self.secret_bundle_path.startswith("/")
            or self.manifest_path == self.secret_bundle_path
        ):
            raise ValueError("production runtime input paths must be distinct absolute paths")
        return self

    @property
    def allowed_host_list(self) -> list[str]:
        return [part.strip() for part in self.allowed_hosts.split(",") if part.strip()]

    @property
    def allowed_origin_list(self) -> list[str]:
        return [part.strip() for part in self.allowed_origins.split(",") if part.strip()]

    @property
    def is_development(self) -> bool:
        return self.environment in {"development", "test"}


@lru_cache
def get_settings() -> RuntimeSettings:
    return RuntimeSettings()
