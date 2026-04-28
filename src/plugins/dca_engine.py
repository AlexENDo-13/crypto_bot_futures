#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCA (Dollar Cost Averaging) Engine v1.0
Усреднение позиции при просадке.
"""
import logging
from dataclasses import dataclass
from typing import List, Optional, Callable

logger = logging.getLogger(__name__)

@dataclass
class DCAConfig:
    symbol: str
    initial_size: float = 0.01
    max_levels: int = 5
    price_step_pct: float = 2.0
    size_multiplier: float = 1.5
    take_profit_pct: float = 1.5
    stop_loss_pct: float = 10.0
    trailing_tp: bool = True

@dataclass
class DCALevel:
    index: int
    trigger_price: float
    size: float
    order_id: Optional[str] = None
    filled: bool = False

class DCAEngine:
    def __init__(self, order_manager, position_tracker, config: DCAConfig, state_manager=None):
        self.om = order_manager
        self.pt = position_tracker
        self.cfg = config
        self.state = state_manager
        self.levels: List[DCALevel] = []
        self.active = False
        self._avg_price = 0.0
        self._total_size = 0.0
        self._tp_order_id: Optional[str] = None
        self._callbacks: List[Callable] = []
        self._build_levels()

    def _build_levels(self):
        self.levels.clear()
        price = 0
        size = self.cfg.initial_size
        for i in range(self.cfg.max_levels):
            self.levels.append(DCALevel(index=i, trigger_price=price, size=size))
            size *= self.cfg.size_multiplier

    def start(self, entry_price: float, side: str = "buy"):
        self._avg_price = entry_price
        self._total_size = self.cfg.initial_size
        self.active = True
        for i, level in enumerate(self.levels):
            drop = self.cfg.price_step_pct * (i + 1)
            level.trigger_price = entry_price * (1 - drop / 100)
            level.filled = False
            level.order_id = None
        self._update_take_profit(side)
        logger.info(f"DCA started @ {entry_price}, {len(self.levels)} levels")
        self._persist_state()

    def on_price_update(self, current_price: float, side: str = "buy"):
        if not self.active:
            return
        for level in self.levels:
            if level.filled or level.order_id:
                continue
            if current_price <= level.trigger_price:
                self._execute_dca_level(level, side)

    def _execute_dca_level(self, level: DCALevel, side: str):
        try:
            order_id = self.om.place_market_order(
                symbol=self.cfg.symbol,
                side=side,
                amount=level.size
            )
            level.order_id = order_id
            level.filled = True
            old_value = self._avg_price * self._total_size
            new_value = level.trigger_price * level.size
            self._total_size += level.size
            self._avg_price = (old_value + new_value) / self._total_size
            logger.info(f"DCA level {level.index} filled @ {level.trigger_price}, "
                        f"new avg={self._avg_price:.4f}, size={self._total_size:.4f}")
            self._update_take_profit(side)
            self._persist_state()
            for cb in self._callbacks:
                cb("dca_fill", level, self._avg_price)
        except Exception as e:
            logger.error(f"DCA level execution failed: {e}")

    def _update_take_profit(self, side: str):
        if self._tp_order_id:
            try:
                self.om.cancel_order(self.cfg.symbol, self._tp_order_id)
            except Exception:
                pass
        tp_price = self._avg_price * (1 + self.cfg.take_profit_pct / 100)
        try:
            self._tp_order_id = self.om.place_limit_order(
                symbol=self.cfg.symbol,
                side="sell" if side == "buy" else "buy",
                amount=self._total_size,
                price=round(tp_price, 4)
            )
        except Exception as e:
            logger.error(f"TP update failed: {e}")

    def stop(self):
        self.active = False
        if self._tp_order_id:
            try:
                self.om.cancel_order(self.cfg.symbol, self._tp_order_id)
            except Exception:
                pass
        logger.info("DCA stopped")
        self._persist_state()

    def get_stats(self) -> dict:
        filled = sum(1 for l in self.levels if l.filled)
        return {
            "active": self.active,
            "avg_price": self._avg_price,
            "total_size": self._total_size,
            "levels_filled": filled,
            "levels_total": len(self.levels),
            "unrealized_pnl": 0.0,
        }

    def _persist_state(self):
        if self.state:
            self.state.save("dca_engine", {
                "config": self.cfg.__dict__,
                "avg_price": self._avg_price,
                "total_size": self._total_size,
                "levels": [(l.index, l.trigger_price, l.filled) for l in self.levels],
                "active": self.active,
            })

    def add_callback(self, callback: Callable):
        self._callbacks.append(callback)
