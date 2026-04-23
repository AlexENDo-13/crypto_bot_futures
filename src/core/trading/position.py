#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Position — модель данных для торговой позиции.
"""
import datetime
from typing import Optional
from enum import Enum


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ExitReason(str, Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"
    TIME_EXIT = "TIME_EXIT"
    EMERGENCY = "EMERGENCY"
    MANUAL = "MANUAL"
    EXCHANGE_CLOSE = "EXCHANGE_CLOSE"


class Position:
    """Представляет открытую торговую позицию."""

    def __init__(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        entry_price: float,
        leverage: int = 1,
        stop_loss_price: float = 0.0,
        take_profit_price: float = 0.0,
        strategy: str = "default",
        entry_time: datetime.datetime = None,
    ):
        self.symbol = symbol
        self.side = side
        self.quantity = abs(quantity)
        self.entry_price = entry(entry_price)
        self.leverage = leverage
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price
        self.strategy = strategy
        self.entry_time = entry_time or datetime.datetime.utcnow()

        # Runtime tracking
        self.current_price = entry_price
        self.max_price_seen = entry_price
        self.min_price_seen = entry_price
        self.unrealized_pnl = 0.0
        self.unrealized_pnl_percent = 0.0
        self.closed = False
        self.exit_reason: Optional[ExitReason] = None
        self.exit_price: float = 0.0
        self.exit_time: Optional[datetime.datetime] = None
        self.realized_pnl: float = 0.0
        self.commission: float = 0.0

    def update_market_price(self, price: float):
        """Обновляет текущую цену и пересчитывает PnL."""
        if price <= 0:
            return
        self.current_price = price

        if self.side == OrderSide.BUY:
            self.max_price_seen = max(self.max_price_seen, price)
            self.min_price_seen = min(self.min_price_seen, price)
            self.unrealized_pnl = (price - self.entry_price) * self.quantity
        else:
            self.max_price_seen = max(self.max_price_seen, price)
            self.min_price_seen = min(self.min_price_seen, price)
            self.unrealized_pnl = (self.entry_price - price) * self.quantity

        margin = self.entry_price * self.quantity / self.leverage
        if margin > 0:
            self.unrealized_pnl_percent = (self.unrealized_pnl / margin) * 100
        else:
            self.unrealized_pnl_percent = 0.0

    def calculate_pnl_percent(self) -> float:
        """Возвращает текущий PnL в процентах."""
        return self.unrealized_pnl_percent

    def close(self, exit_price: float, reason: ExitReason, commission: float = 0.0):
        """Закрывает позицию."""
        self.exit_price = exit_price
        self.exit_reason = reason
        self.exit_time = datetime.datetime.utcnow()
        self.closed = True
        self.commission = commission

        if self.side == OrderSide.BUY:
            self.realized_pnl = (exit_price - self.entry_price) * self.quantity - commission
        else:
            self.realized_pnl = (self.entry_price - exit_price) * self.quantity - commission

        margin = self.entry_price * self.quantity / self.leverage
        if margin > 0:
            self.realized_pnl_percent = (self.realized_pnl / margin) * 100
        else:
            self.realized_pnl_percent = 0.0

    def to_dict(self) -> dict:
        """Сериализует позицию в словарь."""
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "leverage": self.leverage,
            "current_price": self.current_price,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_percent": self.unrealized_pnl_percent,
            "max_price_seen": self.max_price_seen,
            "min_price_seen": self.min_price_seen,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "strategy": self.strategy,
            "closed": self.closed,
            "exit_reason": self.exit_reason.value if self.exit_reason else None,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "realized_pnl": self.realized_pnl,
            "realized_pnl_percent": getattr(self, "realized_pnl_percent", 0.0),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Position":
        """Десериализует позицию из словаря."""
        pos = cls(
            symbol=data.get("symbol", ""),
            side=OrderSide(data.get("side", "BUY")),
            quantity=float(data.get("quantity", 0)),
            entry_price=float(data.get("entry_price", 0)),
            leverage=int(data.get("leverage", 1)),
            stop_loss_price=float(data.get("stop_loss_price", 0)),
            take_profit_price=float(data.get("take_profit_price", 0)),
            strategy=data.get("strategy", "default"),
            entry_time=datetime.datetime.fromisoformat(data["entry_time"]) if data.get("entry_time") else None,
        )
        pos.current_price = float(data.get("current_price", pos.entry_price))
        pos.max_price_seen = float(data.get("max_price_seen", pos.entry_price))
        pos.min_price_seen = float(data.get("min_price_seen", pos.entry_price))
        pos.unrealized_pnl = float(data.get("unrealized_pnl", 0))
        pos.unrealized_pnl_percent = float(data.get("unrealized_pnl_percent", 0))
        pos.closed = data.get("closed", False)
        pos.exit_price = float(data.get("exit_price", 0))
        pos.realized_pnl = float(data.get("realized_pnl", 0))
        if data.get("exit_time"):
            pos.exit_time = datetime.datetime.fromisoformat(data["exit_time"])
        if data.get("exit_reason"):
            pos.exit_reason = ExitReason(data["exit_reason"])
        return pos
