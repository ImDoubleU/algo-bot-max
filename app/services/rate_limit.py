from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int | None = None


class InMemoryRateLimiter:
    """Local MVP limiter. Replace with Redis-backed storage before production."""

    def __init__(self, *, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
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


student_id_entry_limiter = InMemoryRateLimiter(max_attempts=8, window_seconds=15 * 60)
