from app.core.config import get_settings
from app.manifest.loader import load_manifest
from app.server.factory import build_app

settings = get_settings()
manifest = load_manifest(settings.manifest_path)
app = build_app(manifest, settings)
