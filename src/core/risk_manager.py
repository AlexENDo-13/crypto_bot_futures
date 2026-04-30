"""Risk management module."""
from typing import List, Dict, Any
from src.core.models import Signal, Position
from src.core.bot_logger import BotLogger


class RiskManager:
    """Управление рисками."""

    def __init__(self, settings, logger: BotLogger):
        self.settings = settings
        self.logger = logger
        self.daily_pnl = 0.0
        self.daily_loss_limit = settings.get("circuit_breaker_daily_loss", 10.0)

    def can_open_position(self, signal: Signal, positions: List[Position]) -> bool:
        max_positions = self.settings.get("max_positions", 3)
        if len(positions) >= max_positions:
            self.logger.info(f"Max positions reached: {len(positions)}/{max_positions}")
            return False

        if self.daily_pnl <= -self.daily_loss_limit:
            self.logger.warning("Circuit breaker: daily loss limit reached")
            return False

        return True

    def update_pnl(self, pnl: float):
        self.daily_pnl += pnl

    def calculate_position_size(self, balance: float, risk_percent: float, 
                                 entry: float, stop_loss: float, leverage: int) -> float:
        risk_amount = balance * (risk_percent / 100)
        price_diff = abs(entry - stop_loss)
        if price_diff == 0:
            return 0.0
        raw_size = risk_amount / price_diff
        return round(raw_size, 4)
