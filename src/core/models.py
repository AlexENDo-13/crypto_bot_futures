"""Data models for positions, orders, signals."""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class Signal:
    symbol: str
    side: str  # LONG / SHORT
    signal_type: str
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    timeframe: str
    indicators: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Position:
    symbol: str
    side: str
    entry_price: float
    quantity: float
    leverage: int
    stop_loss: float
    take_profit: float
    order_id: str = ""
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    status: str = "OPEN"
    opened_at: datetime = field(default_factory=datetime.now)
    partial_closed: bool = False

    def calculate_pnl_percent(self, current_price: float) -> float:
        if self.entry_price == 0:
            return 0.0
        if self.side == "LONG":
            return ((current_price - self.entry_price) / self.entry_price) * 100 * self.leverage
        else:
            return ((self.entry_price - current_price) / self.entry_price) * 100 * self.leverage


@dataclass
class Order:
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    order_id: str = ""
    status: str = "PENDING"
