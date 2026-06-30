from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.core.config import get_settings


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int | None = None


class RateLimiter(Protocol):
    def check(self, key: str) -> RateLimitResult: ...


class InMemoryRateLimiter:
    def __init__(self, *, max_attempts: int, window_seconds: int) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be greater than 0")
        if window_seconds < 1:
            raise ValueError("window_seconds must be greater than 0")
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.window = timedelta(seconds=window_seconds)
        self._attempts: dict[str, deque[datetime]] = defaultdict(deque)

    def check(self, key: str) -> RateLimitResult:
        now = datetime.now(UTC)
        attempts = self._attempts[key]

        while attempts and now - attempts[0] > self.window:
            attempts.popleft()

        if len(attempts) >= self.max_attempts:
            retry_after = max(1, int((self.window - (now - attempts[0])).total_seconds()))
            return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

        attempts.append(now)
        return RateLimitResult(allowed=True)


class RedisRateLimiter:
    def __init__(
        self,
        *,
        redis_url: str,
        max_attempts: int,
        window_seconds: int,
        fallback: InMemoryRateLimiter | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be greater than 0")
        if window_seconds < 1:
            raise ValueError("window_seconds must be greater than 0")
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.fallback = fallback or InMemoryRateLimiter(
            max_attempts=max_attempts,
            window_seconds=window_seconds,
        )
        try:
            import redis
        except ImportError as exc:  # pragma: no cover - dependency is declared in requirements
            raise RuntimeError("Пакет redis не установлен") from exc

        self.client = redis.Redis.from_url(
            redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        )

    def check(self, key: str) -> RateLimitResult:
        redis_key = f"rate-limit:{key}"
        try:
            count = int(self.client.incr(redis_key))
            if count == 1:
                self.client.expire(redis_key, self.window_seconds)
            ttl = self.client.ttl(redis_key)
        except Exception:  # noqa: BLE001
            return self.fallback.check(key)

        if count > self.max_attempts:
            retry_after = ttl if isinstance(ttl, int) and ttl > 0 else self.window_seconds
            return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

        return RateLimitResult(allowed=True)


def build_rate_limiter(
    *,
    backend: str,
    redis_url: str,
    max_attempts: int,
    window_seconds: int,
) -> RateLimiter:
    backend = backend.lower()
    if max_attempts < 1:
        max_attempts = 8
    if window_seconds < 1:
        window_seconds = 15 * 60

    fallback = InMemoryRateLimiter(max_attempts=max_attempts, window_seconds=window_seconds)
    if backend == "redis":
        try:
            return RedisRateLimiter(
                redis_url=redis_url,
                max_attempts=max_attempts,
                window_seconds=window_seconds,
                fallback=fallback,
            )
        except RuntimeError:
            return fallback
    return fallback


settings = get_settings()
student_id_entry_limiter = build_rate_limiter(
    backend=settings.rate_limit_backend,
    redis_url=settings.redis_url,
    max_attempts=settings.rate_limit_max_attempts,
    window_seconds=settings.rate_limit_window_seconds,
)
