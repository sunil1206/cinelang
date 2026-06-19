"""
Redis cache with graceful degradation.
If Redis is unavailable, all operations silently no-op.
"""
from __future__ import annotations
import json
import logging
from typing import Any

log = logging.getLogger(__name__)
_client = None
_unavailable = False


def _get_client():
    global _client, _unavailable
    if _unavailable:
        return None
    if _client is not None:
        return _client
    try:
        import redis
        from app.config import get_settings
        settings = get_settings()
        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=1.0)
        _client.ping()
        log.info("Redis connected at %s", settings.redis_url)
        return _client
    except Exception as exc:
        log.warning("Redis unavailable — cache disabled: %s", exc)
        _unavailable = True
        return None


def get(key: str) -> dict | None:
    client = _get_client()
    if not client:
        return None
    try:
        raw = client.get(f"cinelang:{key}")
        return json.loads(raw) if raw else None
    except Exception:
        return None


def set(key: str, value: Any, ttl: int | None = None) -> None:
    client = _get_client()
    if not client:
        return
    try:
        from app.config import get_settings
        ttl = ttl or get_settings().cache_ttl_seconds
        client.setex(f"cinelang:{key}", ttl, json.dumps(value, default=str))
    except Exception:
        pass


def delete(key: str) -> None:
    client = _get_client()
    if not client:
        return
    try:
        client.delete(f"cinelang:{key}")
    except Exception:
        pass


def flush_pattern(pattern: str) -> int:
    client = _get_client()
    if not client:
        return 0
    try:
        keys = client.keys(f"cinelang:{pattern}")
        if keys:
            return client.delete(*keys)
        return 0
    except Exception:
        return 0


def is_healthy() -> bool:
    client = _get_client()
    if not client:
        return False
    try:
        client.ping()
        return True
    except Exception:
        return False
