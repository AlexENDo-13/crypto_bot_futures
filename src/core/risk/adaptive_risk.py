"""
Adaptive Risk Module
Живая шкала риска, каскадные стопы, дневной circuit breaker, корреляционная защита.
"""

import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum

from src.core.logger import BotLogger


class RiskRegime(Enum):
    SURVIVAL = "survival"
    BOOST = "boost"
    ACCUMULATION = "accumulation"
    PROTECTION = "protection"


class AntiChase:
    def __init__(self, logger: BotLogger):
        self.logger = logger
        self.recent_losses: List[Tuple[str, float]] = []
        self.forced_cooldown_until: Optional[float] = None

    def record_loss(self, symbol: str):
        now = time.time()
        self.recent_losses.append((symbol, now))
        self.recent_losses = [(s, t) for s, t in self.recent_losses if now - t < 600]

        if len(self.recent_losses) >= 3:
            self.logger.warning("Обнаружена догонялка! Принудительный кулдаун 30 минут.")
            self.forced_cooldown_until = now + 1800

    def can_trade(self) -> Tuple[bool, str]:
        if self.forced_cooldown_until and time.time() < self.forced_cooldown_until:
            remaining = int(self.forced_cooldown_until - time.time())
            return False, f"Анти-догонялка активна, ещё {remaining} сек"
        return True, ""