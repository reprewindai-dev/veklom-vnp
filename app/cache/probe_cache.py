"""Redis cache for probe event results to avoid redundant processing."""
from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as aioredis

import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("PROBE_CACHE_TTL", "300"))  # 5 min default

_pool: Optional[aioredis.Redis] = None


def _client() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _pool


def _key(probe_id: str) -> str:
    return f"vnp:probe:{probe_id}"


async def get_cached_probe(probe_id: str) -> Optional[dict[str, Any]]:
    raw = await _client().get(_key(probe_id))
    return json.loads(raw) if raw else None


async def set_cached_probe(probe_id: str, data: dict[str, Any], ttl: int = CACHE_TTL) -> None:
    await _client().setex(_key(probe_id), ttl, json.dumps(data))


async def invalidate_probe(probe_id: str) -> None:
    await _client().delete(_key(probe_id))
