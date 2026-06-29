from app.services.rate_limit import InMemoryRateLimiter


def test_in_memory_rate_limiter_blocks_after_limit() -> None:
    limiter = InMemoryRateLimiter(max_attempts=2, window_seconds=60)

    assert limiter.check("key").allowed is True
    assert limiter.check("key").allowed is True

    blocked = limiter.check("key")
    assert blocked.allowed is False
    assert blocked.retry_after_seconds is not None
