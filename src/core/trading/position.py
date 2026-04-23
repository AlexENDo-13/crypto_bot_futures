#!/usr/bin/env python3
import datetime
from typing import Optional, Dict, Any
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
    PARTIAL_CLOSE = "PARTIAL_CLOSE"
    BREAKEVEN = "BREAKEVEN"

class Position:
    def __init__(self, symbol, side, quantity, entry_price, leverage=1, stop_loss_price=0.0, take_profit_price=0.0, strategy="default", entry_time=None, order_id=None, sl_order_id=None, tp_order_id=None):
        self.symbol = symbol
        self.side = side
        self.initial_quantity = abs(float(quantity))
        self.quantity = abs(float(quantity))
        self.entry_price = float(entry_price)
        self.leverage = int(leverage)
        self.stop_loss_price = float(stop_loss_price)
        self.take_profit_price = float(take_profit_price)
        self.initial_sl = float(stop_loss_price)
        self.initial_tp = float(take_profit_price)
        self.strategy = strategy
        self.entry_time = entry_time or datetime.datetime.utcnow()
        self.order_id = order_id or ""
        self.sl_order_id = sl_order_id or ""
        self.tp_order_id = tp_order_id or ""
        self.current_price = float(entry_price)
        self.max_price_seen = float(entry_price)
        self.min_price_seen = float(entry_price)
        self.unrealized_pnl = 0.0
        self.unrealized_pnl_percent = 0.0
        self.closed = False
        self.exit_reason = None
        self.exit_price = 0.0
        self.exit_time = None
        self.realized_pnl = 0.0
        self.realized_pnl_percent = 0.0
        self.commission = 0.0
        self.partial_closes = []
        self.trailing_activated = False
        self.trailing_stop_price = 0.0
        self.breakeven_moved = False

    def update_market_price(self, price):
        if price <= 0: return
        self.current_price = price
        self.max_price_seen = max(self.max_price_seen, price)
        self.min_price_seen = min(self.min_price_seen, price)
        if self.side == OrderSide.BUY:
            self.unrealized_pnl = (price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - price) * self.quantity
        margin = self.entry_price * self.quantity / self.leverage if self.quantity > 0 else 1.0
        self.unrealized_pnl_percent = (self.unrealized_pnl / margin) * 100 if margin > 0 else 0.0

    def calculate_pnl_percent(self): return self.unrealized_pnl_percent

    def update_trailing_stop(self, distance_pct):
        if self.side == OrderSide.BUY:
            new_trail = self.max_price_seen * (1 - distance_pct / 100)
            if new_trail > self.trailing_stop_price or self.trailing_stop_price == 0:
                self.trailing_stop_price = new_trail
        else:
            new_trail = self.min_price_seen * (1 + distance_pct / 100)
            if new_trail < self.trailing_stop_price or self.trailing_stop_price == 0:
                self.trailing_stop_price = new_trail

    def move_to_breakeven(self):
        if not self.breakeven_moved:
            self.stop_loss_price = self.entry_price
            self.breakeven_moved = True
            return True
        return False

    def partial_close(self, percent, exit_price, commission=0.0):
        if percent <= 0 or percent > 1 or self.quantity <= 0: return 0.0
        close_qty = self.quantity * percent
        self.quantity -= close_qty
        if self.side == OrderSide.BUY:
            pnl = (exit_price - self.entry_price) * close_qty - commission
        else:
            pnl = (self.entry_price - exit_price) * close_qty - commission
        self.partial_closes.append({"time": datetime.datetime.utcnow().isoformat(), "price": exit_price, "quantity": close_qty, "percent": percent, "pnl": pnl})
        self.realized_pnl += pnl
        return pnl

    def close(self, exit_price, reason, commission=0.0):
        self.exit_price = float(exit_price)
        self.exit_reason = reason
        self.exit_time = datetime.datetime.utcnow()
        self.closed = True
        self.commission = commission
        if self.side == OrderSide.BUY:
            self.realized_pnl += (exit_price - self.entry_price) * self.quantity - commission
        else:
            self.realized_pnl += (self.entry_price - exit_price) * self.quantity - commission
        margin = self.entry_price * self.initial_quantity / self.leverage
        self.realized_pnl_percent = (self.realized_pnl / margin) * 100 if margin > 0 else 0.0
        self.quantity = 0

    def to_dict(self):
        return {"symbol":self.symbol,"side":self.side.value,"initial_quantity":self.initial_quantity,"quantity":self.quantity,"entry_price":self.entry_price,"leverage":self.leverage,"current_price":self.current_price,"stop_loss_price":self.stop_loss_price,"take_profit_price":self.take_profit_price,"trailing_stop_price":self.trailing_stop_price,"unrealized_pnl":self.unrealized_pnl,"unrealized_pnl_percent":self.unrealized_pnl_percent,"max_price_seen":self.max_price_seen,"min_price_seen":self.min_price_seen,"entry_time":self.entry_time.isoformat() if self.entry_time else None,"strategy":self.strategy,"closed":self.closed,"exit_reason":self.exit_reason.value if self.exit_reason else None,"exit_price":self.exit_price,"exit_time":self.exit_time.isoformat() if self.exit_time else None,"realized_pnl":self.realized_pnl,"realized_pnl_percent":self.realized_pnl_percent,"partial_closes":self.partial_closes,"breakeven_moved":self.breakeven_moved,"trailing_activated":self.trailing_activated,"order_id":self.order_id,"sl_order_id":self.sl_order_id,"tp_order_id":self.tp_order_id}

    @classmethod
    def from_dict(cls, data):
        pos = cls(symbol=data.get("symbol",""), side=OrderSide(data.get("side","BUY")), quantity=float(data.get("quantity",0)), entry_price=float(data.get("entry_price",0)), leverage=int(data.get("leverage",1)), stop_loss_price=float(data.get("stop_loss_price",0)), take_profit_price=float(data.get("take_profit_price",0)), strategy=data.get("strategy","default"), entry_time=datetime.datetime.fromisoformat(data["entry_time"]) if data.get("entry_time") else None, order_id=data.get("order_id",""), sl_order_id=data.get("sl_order_id",""), tp_order_id=data.get("tp_order_id",""))
        pos.initial_quantity = float(data.get("initial_quantity", pos.quantity))
        pos.current_price = float(data.get("current_price", pos.entry_price))
        pos.max_price_seen = float(data.get("max_price_seen", pos.entry_price))
        pos.min_price_seen = float(data.get("min_price_seen", pos.entry_price))
        pos.unrealized_pnl = float(data.get("unrealized_pnl", 0))
        pos.unrealized_pnl_percent = float(data.get("unrealized_pnl_percent", 0))
        pos.closed = data.get("closed", False)
        pos.exit_price = float(data.get("exit_price", 0))
        pos.realized_pnl = float(data.get("realized_pnl", 0))
        pos.realized_pnl_percent = float(data.get("realized_pnl_percent", 0))
        pos.partial_closes = data.get("partial_closes", [])
        pos.breakeven_moved = data.get("breakeven_moved", False)
        pos.trailing_activated = data.get("trailing_activated", False)
        pos.trailing_stop_price = float(data.get("trailing_stop_price", 0))
        if data.get("exit_time"): pos.exit_time = datetime.datetime.fromisoformat(data["exit_time"])
        if data.get("exit_reason"): pos.exit_reason = ExitReason(data["exit_reason"])
        return pos
