from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import time


@dataclass
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_epoch: int
    warning: str | None = None
    penalty_seconds: int = 0
    violation_level: int = 0


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._buckets: dict[str, dict[str, int]] = {}
        self._violations: dict[str, dict[str, int]] = {}

    def check(self, *, key: str, limit: int, window_seconds: int = 60) -> RateLimitDecision:
        now = int(time())
        window_start = now - (now % window_seconds)
        reset_epoch = window_start + window_seconds
        bucket_key = f"{key}:{window_start}"

        with self._lock:
            violation = self._violations.get(key, {"count": 0, "blocked_until": 0, "last_violation_at": 0})
            blocked_until = int(violation.get("blocked_until", 0))
            if blocked_until > now:
                return RateLimitDecision(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_epoch=blocked_until,
                    warning="temporary_block",
                    penalty_seconds=blocked_until - now,
                    violation_level=int(violation.get("count", 0)),
                )

            bucket = self._buckets.get(bucket_key)
            if bucket is None:
                bucket = {"count": 0}
                self._buckets[bucket_key] = bucket

            # Opportunistic cleanup for old windows.
            stale_before = window_start - (window_seconds * 3)
            stale_keys = []
            for candidate in self._buckets:
                _, _, suffix = candidate.rpartition(":")
                try:
                    candidate_window = int(suffix)
                except ValueError:
                    continue
                if candidate_window < stale_before:
                    stale_keys.append(candidate)
            for candidate in stale_keys:
                self._buckets.pop(candidate, None)

            stale_violations = []
            for subject, row in self._violations.items():
                last_at = int(row.get("last_violation_at", 0))
                blocked = int(row.get("blocked_until", 0))
                if blocked <= now and last_at and now - last_at > 24 * 60 * 60:
                    stale_violations.append(subject)
            for subject in stale_violations:
                self._violations.pop(subject, None)

            current = int(bucket["count"])
            if current >= limit:
                prior_count = int(violation.get("count", 0))
                next_count = prior_count + 1
                penalty_seconds = 0
                warning = "rate_limit_warning"
                if next_count == 2:
                    penalty_seconds = 60 * 60
                    warning = "rate_limit_block_1h"
                elif next_count == 3:
                    penalty_seconds = 24 * 60 * 60
                    warning = "rate_limit_block_24h"
                elif next_count >= 4:
                    penalty_seconds = 24 * 60 * 60
                    warning = "rate_limit_manual_review"

                blocked_until_next = now + penalty_seconds if penalty_seconds > 0 else now
                self._violations[key] = {
                    "count": next_count,
                    "blocked_until": blocked_until_next,
                    "last_violation_at": now,
                }
                effective_reset = blocked_until_next if penalty_seconds > 0 else reset_epoch
                return RateLimitDecision(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_epoch=effective_reset,
                    warning=warning,
                    penalty_seconds=penalty_seconds,
                    violation_level=next_count,
                )

            bucket["count"] = current + 1
            remaining = max(0, limit - bucket["count"])
            return RateLimitDecision(
                allowed=True,
                limit=limit,
                remaining=remaining,
                reset_epoch=reset_epoch,
                warning=None,
                penalty_seconds=0,
                violation_level=int(violation.get("count", 0)),
            )
