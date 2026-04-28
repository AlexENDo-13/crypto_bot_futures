#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rate Limiter v1.0
Адаптивный throttling + jitter. Защита от бана API.
"""
import logging
import time
import random
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RateLimitConfig:
    requests_per_second: float = 5.0
    burst_size: int = 10
    jitter_ms: tuple = (50, 200)  # Мин/макс jitter в мс
    backoff_multiplier: float = 2.0
    max_backoff_sec: float = 60.0

class RateLimiter:
    """
    Адаптивный rate limiter с jitter.

    Usage:
        limiter = RateLimiter()
        limiter.wait()  # Подождать перед запросом
        # Если получили 429:
        limiter.report_429()
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self._last_request_time = 0.0
        self._current_backoff = 0.0
        self._consecutive_429s = 0
        self._request_count = 0
        self._window_start = time.time()

    def wait(self):
        """Подождать перед запросом (с jitter и backoff)."""
        now = time.time()

        # Базовая задержка между запросами
        min_interval = 1.0 / self.config.requests_per_second
        elapsed = now - self._last_request_time

        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

        # Jitter (рандомизация)
        jitter_ms = random.randint(self.config.jitter_ms[0], self.config.jitter_ms[1])
        time.sleep(jitter_ms / 1000.0)

        # Backoff (если были 429)
        if self._current_backoff > 0:
            logger.debug(f"Rate limiter backoff: {self._current_backoff:.1f}s")
            time.sleep(self._current_backoff)

        self._last_request_time = time.time()
        self._request_count += 1

    def report_429(self):
        """Сообщить о получении 429 Too Many Requests."""
        self._consecutive_429s += 1
        self._current_backoff = min(
            self._current_backoff * self.config.backoff_multiplier 
            if self._current_backoff > 0 else 1.0,
            self.config.max_backoff_sec
        )
        logger.warning(f"429 received. Backoff: {self._current_backoff:.1f}s "
                      f"(consecutive: {self._consecutive_429s})")

    def report_success(self):
        """Сообщить об успешном запросе — сбросить backoff."""
        if self._consecutive_429s > 0:
            self._consecutive_429s = max(0, self._consecutive_429s - 1)
            if self._consecutive_429s == 0:
                self._current_backoff = 0.0
                logger.info("Rate limiter: backoff reset")

    def get_stats(self) -> Dict:
        return {
            "requests_in_window": self._request_count,
            "current_backoff": self._current_backoff,
            "consecutive_429s": self._consecutive_429s,
        }
