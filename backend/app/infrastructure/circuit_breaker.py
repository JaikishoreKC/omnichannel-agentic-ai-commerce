from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class CircuitBreakerOpenError(RuntimeError):
    """Raised when circuit breaker is open and call should fail fast."""


@dataclass(frozen=True)
class CircuitBreakerSnapshot:
    state: str
    failure_count: int
    opened_at_monotonic: float | None


class CircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
    ) -> None:
        self.failure_threshold = max(1, int(failure_threshold))
        self.recovery_timeout_seconds = max(0.01, float(recovery_timeout_seconds))
        self._state = "closed"
        self._failure_count = 0
        self._opened_at_monotonic: float | None = None
        self._lock = RLock()

    @property
    def snapshot(self) -> CircuitBreakerSnapshot:
        with self._lock:
            return CircuitBreakerSnapshot(
                state=self._state,
                failure_count=self._failure_count,
                opened_at_monotonic=self._opened_at_monotonic,
            )

    def call(self, fn: Callable[[], T]) -> T:
        with self._lock:
            self._pre_call_gate()
            in_half_open = self._state == "half_open"

        try:
            value = fn()
        except Exception:
            with self._lock:
                self._on_failure()
            raise

        with self._lock:
            if in_half_open:
                self._state = "closed"
            self._failure_count = 0
            self._opened_at_monotonic = None
        return value

    def _pre_call_gate(self) -> None:
        if self._state == "open":
            if self._opened_at_monotonic is None:
                self._opened_at_monotonic = monotonic()
            elapsed = monotonic() - self._opened_at_monotonic
            if elapsed >= self.recovery_timeout_seconds:
                self._state = "half_open"
                return
            raise CircuitBreakerOpenError("Circuit breaker is open")

    def _on_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            self._state = "open"
            self._opened_at_monotonic = monotonic()
            return
        if self._state == "half_open":
            self._state = "open"
            self._opened_at_monotonic = monotonic()
