"""Presence + rate limit dùng Redis; tự lùi về bộ nhớ trong tiến trình nếu Redis không khả dụng."""
import time
from collections import defaultdict, deque

import redis.asyncio as aioredis

from .config import settings

PRESENCE_WINDOW_S = 120
_redis: aioredis.Redis | None = None
_redis_down_until = 0.0
_mem_presence: dict[str, float] = {}
_mem_hits: dict[str, deque] = defaultdict(deque)


async def _r() -> aioredis.Redis | None:
    global _redis, _redis_down_until
    if time.monotonic() < _redis_down_until:
        return None
    try:
        if _redis is None:
            _redis = aioredis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        await _redis.ping()
        return _redis
    except Exception:
        _redis = None
        _redis_down_until = time.monotonic() + 15
        return None


async def redis_ok() -> bool:
    return await _r() is not None


async def presence_touch(device_id: str) -> None:
    now = time.time()
    r = await _r()
    if r:
        await r.zadd("presence", {device_id: now})
    else:
        _mem_presence[device_id] = now


async def presence_count() -> int:
    cutoff = time.time() - PRESENCE_WINDOW_S
    r = await _r()
    if r:
        await r.zremrangebyscore("presence", 0, cutoff)
        return int(await r.zcard("presence"))
    for k in [k for k, v in _mem_presence.items() if v < cutoff]:
        del _mem_presence[k]
    return len(_mem_presence)


async def online_users() -> dict[str, float]:
    """user_id -> thời điểm hoạt động cuối, cho các tài khoản đang online (trong PRESENCE_WINDOW_S)."""
    cutoff = time.time() - PRESENCE_WINDOW_S
    r = await _r()
    if r:
        rows = await r.zrangebyscore("presence", cutoff, "+inf", withscores=True)
        out = {(k.decode() if isinstance(k, bytes) else k): s for k, s in rows}
    else:
        out = dict(_mem_presence)
        out = {k: v for k, v in out.items() if v >= cutoff}
    return {k[2:]: v for k, v in out.items() if k.startswith("u:")}


async def rate_hit(key: str, limit: int, window_s: int) -> int | None:
    """Trả Retry-After (giây) nếu vượt hạn mức, ngược lại None."""
    r = await _r()
    if r:
        k = f"rl:{key}"
        n = await r.incr(k)
        if n == 1:
            await r.expire(k, window_s)
        if n > limit:
            return max(int(await r.ttl(k)), 1)
        return None
    now = time.monotonic()
    q = _mem_hits[key]
    while q and now - q[0] > window_s:
        q.popleft()
    if len(q) >= limit:
        return int(window_s - (now - q[0])) + 1
    q.append(now)
    return None
