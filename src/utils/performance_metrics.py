"""
Performance Metrics – метрики разгона.
"""

from typing import Dict, List
from src.core.logger import BotLogger


class PerformanceMetrics:
    def __init__(self, logger: BotLogger, config: Dict):
        self.logger = logger
        self.daily_pnl = 0.0
        self.daily_start_balance = None
        self.weekly_pnl = 0.0
        self.weekly_start_balance = None
        self.trades: List[Dict] = []

    def record_trade(self, symbol: str, price: float, side: str, strategy: str):
        self.trades.append({"symbol": symbol, "entry": price, "side": side, "strategy": strategy, "pnl": None})

    def record_close(self, pnl: float, balance: float, strategy: str = None):
        self.daily_pnl += pnl
        self.weekly_pnl += pnl
        if self.daily_start_balance is None:
            self.daily_start_balance = balance - pnl
        if self.weekly_start_balance is None:
            self.weekly_start_balance = balance - pnl

    def get_daily_pnl_percent(self) -> float:
        if self.daily_start_balance:
            return (self.daily_pnl / self.daily_start_balance) * 100
        return 0.0

    def get_weekly_pnl_percent(self) -> float:
        if self.weekly_start_balance:
            return (self.weekly_pnl / self.weekly_start_balance) * 100
        return 0.0

    def get_win_rate(self) -> float:
        closed = [t for t in self.trades if t.get('pnl') is not None]
        if not closed:
            return 0.0
        return sum(1 for t in closed if t['pnl'] > 0) / len(closed) * 100