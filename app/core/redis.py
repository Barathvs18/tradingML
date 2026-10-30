import redis.asyncio as redis
from app.core.config import settings

redis_client: redis.Redis = None # type: ignore

async def get_redis_client() -> redis.Redis:
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True,
                                      socket_connect_timeout=3, socket_timeout=3, max_connections=50)
    return redis_client

async def close_redis_client():
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None
