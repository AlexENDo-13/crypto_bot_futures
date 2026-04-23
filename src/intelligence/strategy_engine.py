#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StrategyEngine — движок стратегий.
"""
import logging
import time
from typing import Dict, Any

from src.config.settings import Settings

class StrategyEngine:
    """Управление торговыми стратегиями."""

    def __init__(self, logger: logging.Logger, settings: Settings):
        self.logger = logger
        self.settings = settings
        self.last_trade_time = 0
        self.trade_results: list = []
        self.consecutive_losses = 0

    def record_trade_result(self, pnl: float):
        """Записывает результат сделки."""
        self.trade_results.append({"pnl": pnl, "time": time.time()})
        if len(self.trade_results) > 100:
            self.trade_results = self.trade_results[-100:]

        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def get_recent_performance(self, window: int = 10) -> dict:
        """Возвращает статистику последних сделок."""
        recent = self.trade_results[-window:]
        if not recent:
            return {"win_rate": 0, "avg_pnl": 0, "total": 0}

        wins = sum(1 for t in recent if t["pnl"] > 0)
        total_pnl = sum(t["pnl"] for t in recent)
        return {
            "win_rate": wins / len(recent),
            "avg_pnl": total_pnl / len(recent),
            "total": len(recent),
            "consecutive_losses": self.consecutive_losses,
        }
