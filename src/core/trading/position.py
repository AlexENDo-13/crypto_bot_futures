#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Position:
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    quantity: float
    leverage: int
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    entry_time: Optional[datetime] = None
    order_id: Optional[str] = None
    is_closed: bool = False

    def __post_init__(self):
        if self.entry_time is None:
            self.entry_time = datetime.now()

    @property
    def side(self):
        return self.direction

    def update_market_price(self, price: float):
        self.current_price = price

    def calculate_unrealized_pnl(self) -> float:
        if not hasattr(self, 'current_price'):
            return 0.0
        if self.direction == 'LONG':
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity
