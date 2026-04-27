#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Position model with safe PnL calculations."""
from enum import Enum
from datetime import datetime
from typing import Optional, List

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class ExitReason(Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"
    TIME_EXIT = "TIME_EXIT"
    MANUAL = "MANUAL"
    EXCHANGE_CLOSE = "EXCHANGE_CLOSE"
    UNKNOWN = "UNKNOWN"

class Position:
    def __init__(self, symbol: str, side: OrderSide, quantity: float, entry_price: float,
                 leverage: int = 1, stop_loss_price: float = 0.0, take_profit_price: float = 0.0,
                 strategy: str = "macd_rsi", order_id: str = "", sl_order_id: str = "",
                 tp_order_id: str = ""):
        self.symbol = symbol
        self.side = side
        self.quantity = max(0.0, float(quantity))
        self.initial_quantity = max(0.0, float(quantity))
        self.entry_price = max(0.0, float(entry_price))
        self.leverage = max(1, int(leverage))
        self.stop_loss_price = float(stop_loss_price)
        self.take_profit_price = float(take_profit_price)
        self.strategy = strategy
        self.order_id = str(order_id)
        self.sl_order_id = str(sl_order_id)
        self.tp_order_id = str(tp_order_id)
        self.entry_time = datetime.utcnow()
        self.exit_time: Optional[datetime] = None
        self.closed = False
        self.exit_price = 0.0
        self.exit_reason: Optional[ExitReason] = None
        self.current_price = self.entry_price
        self.unrealized_pnl = 0.0
        self.realized_pnl = 0.0
        self.realized_pnl_percent = 0.0
        self.trailing_activated = False
        self.trailing_stop_price = 0.0
        self.partial_closes: List[dict] = []
        self.max_profit_pct = 0.0
        self.max_loss_pct = 0.0
        self._last_update = datetime.utcnow()

    def update_market_price(self, price: float):
        price = float(price)
        if price <= 0:
            return
        self.current_price = price
        pnl_pct = self.calculate_pnl_percent()
        self.unrealized_pnl = self.quantity * self.entry_price * (pnl_pct / 100.0) * self.leverage if self.entry_price > 0 else 0.0
        if pnl_pct > self.max_profit_pct:
            self.max_profit_pct = pnl_pct
        if pnl_pct < self.max_loss_pct:
            self.max_loss_pct = pnl_pct
        self._last_update = datetime.utcnow()

    def calculate_pnl_percent(self) -> float:
        if self.entry_price <= 0:
            return 0.0
        if self.side == OrderSide.BUY:
            return ((self.current_price - self.entry_price) / self.entry_price) * 100.0 * self.leverage
        else:
            return ((self.entry_price - self.current_price) / self.entry_price) * 100.0 * self.leverage

    def update_trailing_stop(self, distance_percent: float):
        if not self.trailing_activated:
            return
        pnl_pct = self.calculate_pnl_percent()
        if pnl_pct <= 0:
            return
        if self.side == OrderSide.BUY:
            new_stop = self.current_price * (1.0 - distance_percent / 100.0)
            if new_stop > self.trailing_stop_price:
                self.trailing_stop_price = new_stop
        else:
            new_stop = self.current_price * (1.0 + distance_percent / 100.0)
            if new_stop < self.trailing_stop_price or self.trailing_stop_price == 0:
                self.trailing_stop_price = new_stop

    def partial_close(self, close_fraction: float, current_price: float) -> float:
        if self.quantity <= 0 or self.closed:
            return 0.0
        close_qty = self.quantity * close_fraction
        if close_qty <= 0:
            return 0.0
        if self.side == OrderSide.BUY:
            pnl = (current_price - self.entry_price) * close_qty * self.leverage
        else:
            pnl = (self.entry_price - current_price) * close_qty * self.leverage
        self.quantity -= close_qty
        self.partial_closes.append({"fraction": close_fraction, "price": current_price, "pnl": pnl})
        self.realized_pnl += pnl
        return pnl

    def move_to_breakeven(self) -> bool:
        if self.entry_price <= 0:
            return False
        if self.side == OrderSide.BUY:
            if self.stop_loss_price < self.entry_price:
                self.stop_loss_price = self.entry_price * 1.0005
                return True
        else:
            if self.stop_loss_price > self.entry_price:
                self.stop_loss_price = self.entry_price * 0.9995
                return True
        return False

    def close(self, exit_price: float, reason: ExitReason):
        if self.closed:
            return
        self.exit_price = float(exit_price)
        self.exit_time = datetime.utcnow()
        self.exit_reason = reason
        self.closed = True
        if self.side == OrderSide.BUY:
            self.realized_pnl = (self.exit_price - self.entry_price) * self.quantity * self.leverage
        else:
            self.realized_pnl = (self.entry_price - self.exit_price) * self.quantity * self.leverage
        if self.entry_price > 0:
            self.realized_pnl_percent = (self.realized_pnl / (self.entry_price * self.initial_quantity)) * 100.0
        else:
            self.realized_pnl_percent = 0.0
        self.quantity = 0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "initial_quantity": self.initial_quantity,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "exit_price": self.exit_price,
            "leverage": self.leverage,
            "stop_loss": self.stop_loss_price,
            "take_profit": self.take_profit_price,
            "trailing_stop": self.trailing_stop_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "realized_pnl_percent": self.realized_pnl_percent,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "closed": self.closed,
            "exit_reason": self.exit_reason.value if self.exit_reason else None,
            "strategy": self.strategy,
            "partial_closes": self.partial_closes,
            "max_profit_pct": self.max_profit_pct,
            "max_loss_pct": self.max_loss_pct,
        }
