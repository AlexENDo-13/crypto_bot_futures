#!/usr/bin/env python3
"""
Error Pattern Detector (B6) — "3 losses → pause" and other smart patterns.
Detects losing streaks, overtrading, drawdown spikes, and enforces cooling periods.
"""
import json
import os
import time
import logging
from collections import deque
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("CryptoBot.ErrorPatterns")

class ErrorPatternDetector:
    def __init__(self, data_path: str = "logs/error_patterns.json"):
        self.data_path = data_path
        self._loss_streak = 0
        self._win_streak = 0
        self._trade_times: deque = deque(maxlen=100)
        self._daily_losses: deque = deque(maxlen=30)  # Last 30 days
        self._cooldown_until = 0
        self._paused = False
        self._pause_reason = ""
        self._max_loss_streak = 3
        self._max_daily_loss_pct = 8.0
        self._cooldown_seconds = 1800  # 30 min default
        self._overtrade_threshold = 6  # Trades per hour
        self._drawdown_peak = 0.0
        self._current_drawdown = 0.0
        self._load()

    def _load(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._max_loss_streak = data.get("max_loss_streak", 3)
                    self._cooldown_seconds = data.get("cooldown_seconds", 1800)
                    self._overtrade_threshold = data.get("overtrade_threshold", 6)
                logger.info(f"Error patterns loaded: max_loss_streak={self._max_loss_streak}")
            except Exception as e:
                logger.error(f"Error patterns load error: {e}")

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump({
                    "max_loss_streak": self._max_loss_streak,
                    "cooldown_seconds": self._cooldown_seconds,
                    "overtrade_threshold": self._overtrade_threshold,
                    "last_update": time.time()
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error patterns save error: {e}")

    def record_trade(self, pnl: float, balance: float = 100.0):
        """Record trade outcome and check for error patterns."""
        now = time.time()
        self._trade_times.append(now)

        if pnl < 0:
            self._loss_streak += 1
            self._win_streak = 0
            # Track drawdown
            self._current_drawdown += abs(pnl)
            if self._current_drawdown > self._drawdown_peak:
                self._drawdown_peak = self._current_drawdown
        else:
            self._loss_streak = 0
            self._win_streak += 1
            self._current_drawdown = max(0, self._current_drawdown - pnl)

        # Check patterns
        self._check_loss_streak(balance)
        self._check_overtrading()
        self._check_drawdown(balance)

    def _check_loss_streak(self, balance: float):
        if self._loss_streak >= self._max_loss_streak:
            self._trigger_pause(
                f"LOSS STREAK: {self._loss_streak} consecutive losses",
                self._cooldown_seconds * (1 + (self._loss_streak - self._max_loss_streak) * 0.5)
            )

    def _check_overtrading(self):
        hour_ago = time.time() - 3600
        recent_trades = sum(1 for t in self._trade_times if t > hour_ago)
        if recent_trades >= self._overtrade_threshold:
            self._trigger_pause(
                f"OVERTRADING: {recent_trades} trades in last hour",
                900  # 15 min cooldown
            )

    def _check_drawdown(self, balance: float):
        if balance > 0:
            dd_pct = (self._current_drawdown / balance) * 100
            if dd_pct >= self._max_daily_loss_pct:
                self._trigger_pause(
                    f"DRAWDOWN: {dd_pct:.1f}% daily loss limit reached",
                    self._cooldown_seconds * 2
                )

    def _trigger_pause(self, reason: str, duration: float):
        if self._paused:
            return
        self._paused = True
        self._pause_reason = reason
        self._cooldown_until = time.time() + duration
        logger.warning(f"PATTERN TRIGGERED: {reason} — PAUSED for {duration/60:.0f} minutes")

    def can_trade(self) -> Tuple[bool, str]:
        """Check if trading is allowed."""
        if not self._paused:
            return True, "OK"

        now = time.time()
        if now >= self._cooldown_until:
            self._paused = False
            self._pause_reason = ""
            logger.info("PATTERN: Cooldown expired — trading resumed")
            return True, "Cooldown expired"

        remaining = self._cooldown_until - now
        return False, f"PAUSED: {self._pause_reason} — {remaining/60:.0f} min remaining"

    def force_resume(self):
        """Manually resume trading (e.g. from GUI)."""
        self._paused = False
        self._pause_reason = ""
        self._cooldown_until = 0
        self._loss_streak = 0
        logger.info("PATTERN: Manually resumed")

    def get_stats(self) -> Dict[str, Any]:
        now = time.time()
        return {
            "loss_streak": self._loss_streak,
            "win_streak": self._win_streak,
            "paused": self._paused,
            "pause_reason": self._pause_reason,
            "cooldown_remaining": max(0, self._cooldown_until - now),
            "current_drawdown": self._current_drawdown,
            "peak_drawdown": self._drawdown_peak,
            "trades_last_hour": sum(1 for t in self._trade_times if t > now - 3600),
        }

    def set_max_loss_streak(self, n: int):
        self._max_loss_streak = max(1, min(10, n))
        self._save()

    def set_cooldown(self, seconds: float):
        self._cooldown_seconds = max(60, seconds)
        self._save()
