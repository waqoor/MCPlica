import json

from app.core.config import Settings


def render_openapi_artifact(settings: Settings | None = None) -> bytes:
    # Import lazily so schema rendering cannot introduce an app-construction cycle.
    from app.main import create_app

    config = settings or Settings(_env_file=None, env="test")  # pyright: ignore[reportCallIssue]
    schema = create_app(config).openapi()
    return (
        json.dumps(
            schema,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
            separators=(",", ": "),
        )
        + "\n"
    ).encode("utf-8")
