import hashlib
import time
from functools import cache

import redis

from eletric_motor.rag.settings import Settings
from eletric_motor.rag.trace import (
    TraceContext,
    elapsed_ms,
    error_message,
    error_origin,
    log_event,
)

# Cache é otimização, não infraestrutura crítica: após uma falha de conexão o
# módulo desliga pelo resto do processo e a operação segue sem cache.
_unavailable = False


def cache_key(*parts: str) -> str:
    """Stable key from the data that defines the cached result."""
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def cache_get(scope: str, key: str, *, enabled: bool = True) -> str | None:
    settings = Settings()
    if _unavailable or not enabled or not settings.cache_enabled:
        return None
    started = time.perf_counter()
    try:
        value = _client().get(f"{scope}:{key}")
    except redis.RedisError as exc:
        _mark_unavailable(exc, started)
        return None
    log_event(
        "cache.lookup",
        logger_name=__name__,
        context=TraceContext(
            span="cache",
            cache_scope=scope,
            cache_hit=value is not None,
            latency_ms=elapsed_ms(started),
        ),
    )
    return value


def cache_set(scope: str, key: str, value: str, *, enabled: bool = True) -> None:
    settings = Settings()
    if _unavailable or not enabled or not settings.cache_enabled:
        return
    try:
        _client().setex(f"{scope}:{key}", settings.cache_ttl_s, value)
    except redis.RedisError as exc:
        _mark_unavailable(exc, time.perf_counter())


@cache
def _client() -> redis.Redis:
    # Timeouts de 1 s: Redis parado não pode segurar a CLI.
    return redis.Redis.from_url(
        Settings().redis_url,
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=True,
    )


def _mark_unavailable(exc: redis.RedisError, started: float) -> None:
    global _unavailable
    _unavailable = True
    origin = error_origin(exc)
    log_event(
        "cache.unavailable",
        level="warning",
        logger_name=__name__,
        context=TraceContext(
            span="cache",
            latency_ms=elapsed_ms(started),
            error_type=type(exc).__name__,
            error_message=error_message(exc),
            error_file=None if origin is None else origin[0],
            error_line=None if origin is None else origin[1],
            error_function=None if origin is None else origin[2],
        ),
    )
