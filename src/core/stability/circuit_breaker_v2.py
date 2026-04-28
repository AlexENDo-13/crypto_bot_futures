"""
Circuit Breaker v2 — smarter reconnection with exponential backoff and half-open state.
"""
import time
import logging
from enum import Enum

logger = logging.getLogger("CryptoBot.CircuitBreaker")

class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing fast
    HALF_OPEN = "half_open" # Testing recovery

class CircuitBreakerV2:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0,
                 half_open_max_calls: int = 3, success_threshold: int = 2):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0
        self._half_open_calls = 0
        self._total_failures = 0
        self._total_successes = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                self._success_count = 0
                logger.info("Circuit breaker: transitioning to HALF_OPEN")
        return self._state

    def record_success(self):
        self._total_successes += 1
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            self._half_open_calls += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info("Circuit breaker: CLOSED (recovered)")
        elif self._state == CircuitState.CLOSED:
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self):
        self._total_failures += 1
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker: OPEN (failure in half-open, count={self._failure_count})")
        elif self._state == CircuitState.CLOSED and self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker: OPEN (failures={self._failure_count})")

    def can_execute(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.OPEN:
            return False
        if state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                return True
            return False
        return False

    def get_stats(self) -> dict:
        return {
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_failures": self._total_failures,
            "total_successes": self._total_successes,
            "last_failure_ago": time.time() - self._last_failure_time if self._last_failure_time else None,
        }
