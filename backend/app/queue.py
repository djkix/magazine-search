import redis
from rq import Queue

from app.config import get_settings

settings = get_settings()

redis_conn = redis.Redis(host=settings.redis_host, port=settings.redis_port)
ingestion_queue = Queue("ingestion", connection=redis_conn)
