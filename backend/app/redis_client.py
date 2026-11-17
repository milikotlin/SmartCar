import json
from typing import Any

import redis.asyncio as redis

from app.config import settings

_redis = redis.from_url(settings.redis_url, decode_responses=True)


async def get_cached(key: str) -> dict[str, Any] | None:
    raw = await _redis.get(key)
    return json.loads(raw) if raw else None


async def set_cached(key: str, value: dict[str, Any], ttl_seconds: int | None = None) -> None:
    await _redis.set(key, json.dumps(value), ex=ttl_seconds or settings.redis_cache_ttl_seconds)
