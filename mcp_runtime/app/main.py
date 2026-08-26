import uvicorn

from app.core.config import get_settings
from app.core.logging import configure_runtime_logging
from app.manifest.loader import load_manifest
from app.secrets.loader import load_secret_bundle
from app.server.factory import build_app

settings = get_settings()
configure_runtime_logging(settings.log_level)
manifest = load_manifest(
    settings.manifest_path,
    expected_sha256=settings.manifest_sha256,
    max_bytes=settings.max_manifest_bytes,
    runtime_version=settings.runtime_version,
)
secret_bundle = load_secret_bundle(
    settings.secret_bundle_path,
    max_bytes=settings.max_secret_bundle_bytes,
    require_secure_permissions=settings.require_secure_secret_permissions,
)
app = build_app(manifest, secret_bundle, settings)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.runtime_host,
        port=settings.runtime_port,
        workers=1,
        log_level=settings.log_level.lower(),
    )
