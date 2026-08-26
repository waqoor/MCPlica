from redis import Redis
from rq import Queue

from app.core.config import get_settings

settings = get_settings()


def get_queue() -> Queue:
    connection = Redis.from_url(settings.redis_url)
    return Queue(settings.rq_queue, connection=connection)
