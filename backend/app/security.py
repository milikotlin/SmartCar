"""Protection of the write endpoints and of the paid chat endpoint (simple, no user accounts: the SRS requires no login).

* Writing a maintenance or inspection record needs the shared WORKSHOP KEY (header ``X-Write-Key``). Reading stays open, as the dashboard and the registry are.
  Why it matters: a stored inspection result is an INPUT of Model 2, so anyone able to write records for a plate could change the risk shown for somebody else's car.
* No key configured  ->  writing is disabled (fail closed). The key lives in ``.env`` (never in git) and is compared in constant time.
* A fixed-window rate limit per client address slows down key guessing, record flooding and abuse of the chat (every chat call can cost an OpenAI request).
"""
import hmac

from fastapi import HTTPException, Request

from app.config import settings
from app.redis_client import _redis

WRITE_KEY_HEADER = "X-Write-Key"


async def _hit(bucket: str, ident: str, limit: int, window_seconds: int) -> bool:
    """True while the caller is within its quota. Redis failure never blocks the service (the limiter fails open)."""
    key = f"ratelimit:{bucket}:{ident}"
    try:
        n = await _redis.incr(key)
        if n == 1:
            await _redis.expire(key, window_seconds)
        return n <= limit
    except Exception:       # noqa: BLE001 - availability of the demo matters more than the limiter
        return True


def _client_id(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str, limit, window_seconds: int = 60):
    """``limit`` is a number of requests per window, or a function returning it (read at request time, so tests and settings can change it)."""
    async def dependency(request: Request) -> None:
        allowed = limit() if callable(limit) else limit
        if not await _hit(bucket, _client_id(request), allowed, window_seconds):
            raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute and try again.", headers={"Retry-After": str(window_seconds)})

    return dependency


async def require_write_key(request: Request) -> None:
    configured = settings.records_write_key
    if not configured:
        raise HTTPException(status_code=403, detail="Writing records is disabled: no workshop key is configured on the server.")
    given = request.headers.get(WRITE_KEY_HEADER, "")
    if not hmac.compare_digest(given.encode("utf-8"), configured.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Missing or invalid workshop key. Only authorised workshops can add or change records.")
