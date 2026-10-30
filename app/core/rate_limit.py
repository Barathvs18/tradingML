"""Atomic sliding-window limits shared by all API processes."""
from fastapi import Request, HTTPException
import hashlib
import uuid
from redis.exceptions import RedisError
from app.core.redis import get_redis_client

LIMIT_SCRIPT = """
local now = redis.call('TIME')
local seconds = tonumber(now[1]) + tonumber(now[2]) / 1000000
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', seconds - tonumber(ARGV[1]))
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then return 0 end
redis.call('ZADD', KEYS[1], seconds, ARGV[3])
redis.call('EXPIRE', KEYS[1], ARGV[1])
return 1
"""

class RateLimiter:
    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window

    async def __call__(self, request: Request):
        redis = await get_redis_client()
        ip = request.client.host if request.client else "unknown"
        route = request.scope.get("route")
        path = route.path if route else request.url.path
        digest = hashlib.sha256(ip.encode()).hexdigest()
        key = f"rate_limit:{path}:{self.requests}:{self.window}:{digest}"
        try:
            allowed = await redis.eval(LIMIT_SCRIPT, 1, key, self.window, self.requests, str(uuid.uuid4()))
        except RedisError as exc:
            raise HTTPException(503, "Service temporarily unavailable", headers={"Retry-After": "5"}) from exc
        if not allowed:
            raise HTTPException(429, "Too Many Requests", headers={"Retry-After": str(self.window)})
