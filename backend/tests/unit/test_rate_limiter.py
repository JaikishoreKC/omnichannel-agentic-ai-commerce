from app.infrastructure.rate_limiter import SlidingWindowRateLimiter


def test_sliding_window_rate_limiter_blocks_after_limit() -> None:
    limiter = SlidingWindowRateLimiter()
    key = "scope:subject"

    first = limiter.check(key=key, limit=2, window_seconds=60)
    second = limiter.check(key=key, limit=2, window_seconds=60)
    third = limiter.check(key=key, limit=2, window_seconds=60)

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.remaining == 0


def test_sliding_window_rate_limiter_applies_progressive_penalties() -> None:
    limiter = SlidingWindowRateLimiter()
    key = "scope:abusive"

    first = limiter.check(key=key, limit=1, window_seconds=60)
    assert first.allowed is True

    second = limiter.check(key=key, limit=1, window_seconds=60)
    assert second.allowed is False
    assert second.warning == "rate_limit_warning"
    assert second.penalty_seconds == 0

    third = limiter.check(key=key, limit=1, window_seconds=60)
    assert third.allowed is False
    assert third.warning == "rate_limit_block_1h"
    assert third.penalty_seconds == 3600

    during_block = limiter.check(key=key, limit=1, window_seconds=60)
    assert during_block.allowed is False
    assert during_block.warning == "temporary_block"
