import pytest

from app.services.rate_limit import InMemoryRateLimiter, RedisRateLimiter, build_rate_limiter


def test_in_memory_rate_limiter_blocks_after_limit() -> None:
    limiter = InMemoryRateLimiter(max_attempts=2, window_seconds=60)

    assert limiter.check("key").allowed is True
    assert limiter.check("key").allowed is True

    blocked = limiter.check("key")
    assert blocked.allowed is False
    assert blocked.retry_after_seconds is not None


def test_build_rate_limiter_normalizes_invalid_limits() -> None:
    limiter = build_rate_limiter(
        backend="memory",
        redis_url="redis://unused",
        max_attempts=0,
        window_seconds=0,
    )

    assert limiter.check("key").allowed is True


@pytest.mark.parametrize(
    ("max_attempts", "window_seconds"),
    [(0, 60), (2, 0)],
)
def test_in_memory_rate_limiter_rejects_invalid_limits(
    max_attempts: int,
    window_seconds: int,
) -> None:
    with pytest.raises(ValueError):
        InMemoryRateLimiter(max_attempts=max_attempts, window_seconds=window_seconds)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key: str, seconds: int) -> None:
        self.ttls[key] = seconds

    def ttl(self, key: str) -> int:
        return self.ttls.get(key, -1)


class BrokenRedis:
    def incr(self, key: str) -> int:
        raise RuntimeError(f"{key} unavailable")


def make_redis_limiter(
    client: object,
    fallback: InMemoryRateLimiter | None = None,
) -> RedisRateLimiter:
    limiter = RedisRateLimiter.__new__(RedisRateLimiter)
    limiter.max_attempts = 2
    limiter.window_seconds = 60
    limiter.fallback = fallback or InMemoryRateLimiter(max_attempts=2, window_seconds=60)
    limiter.client = client
    return limiter


def test_redis_rate_limiter_blocks_after_limit() -> None:
    limiter = make_redis_limiter(FakeRedis())

    assert limiter.check("student").allowed is True
    assert limiter.check("student").allowed is True

    blocked = limiter.check("student")
    assert blocked.allowed is False
    assert blocked.retry_after_seconds == 60


def test_redis_rate_limiter_falls_back_to_memory_on_client_error() -> None:
    limiter = make_redis_limiter(
        BrokenRedis(),
        fallback=InMemoryRateLimiter(max_attempts=1, window_seconds=60),
    )

    assert limiter.check("student").allowed is True

    blocked = limiter.check("student")
    assert blocked.allowed is False
    assert blocked.retry_after_seconds is not None
