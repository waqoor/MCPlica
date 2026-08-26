from redis import Redis
from rq import Queue

from app.core.config import get_settings

settings = get_settings()


def get_build_queue() -> Queue:
    connection = Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
        settings.redis_url
    )
    return Queue(settings.build_queue_name, connection=connection)


def get_deployment_queue() -> Queue:
    connection = Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
        settings.redis_url
    )
    return Queue(settings.deployment_queue_name, connection=connection)
