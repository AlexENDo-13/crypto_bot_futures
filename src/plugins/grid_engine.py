#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grid Trading Engine v1.0
Сеточная стратегия для боковых рынков.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)

class GridSide(Enum):
    BUY = "buy"
    SELL = "sell"

@dataclass
class GridLevel:
    price: float
    side: GridSide
    size: float
    order_id: Optional[str] = None
    filled: bool = False

@dataclass
class GridConfig:
    symbol: str
    upper_price: float
    lower_price: float
    grid_count: int = 10
    order_size: float = 0.01
    max_position: float = 1.0
    tp_percent: float = 1.0
    sl_percent: float = 5.0
    rebalance: bool = True

class GridEngine:
    def __init__(self, order_manager, config: GridConfig, state_manager=None):
        self.om = order_manager
        self.cfg = config
        self.state = state_manager
        self.levels: List[GridLevel] = []
        self.active = False
        self._callbacks: List[Callable] = []
        self._total_profit = 0.0
        self._step = (config.upper_price - config.lower_price) / config.grid_count

    def initialize(self):
        if self.active:
            logger.warning("Grid already active")
            return
        self.levels.clear()
        for i in range(self.cfg.grid_count + 1):
            price = self.cfg.lower_price + self._step * i
            side = GridSide.BUY if i % 2 == 0 else GridSide.SELL
            level = GridLevel(price=round(price, 4), side=side, size=self.cfg.order_size)
            self.levels.append(level)
            self._place_limit(level)
        self.active = True
        logger.info(f"Grid initialized: {self.cfg.symbol} {len(self.levels)} levels")
        self._persist_state()

    def _place_limit(self, level: GridLevel):
        try:
            order_id = self.om.place_limit_order(
                symbol=self.cfg.symbol,
                side=level.side.value,
                amount=level.size,
                price=level.price
            )
            level.order_id = order_id
            logger.debug(f"Placed {level.side.value} limit @ {level.price}")
        except Exception as e:
            logger.error(f"Failed to place grid order: {e}")

    def on_fill(self, order_id: str, filled_price: float, filled_qty: float):
        for level in self.levels:
            if level.order_id == order_id and not level.filled:
                level.filled = True
                profit = self._calculate_fill_profit(level, filled_price, filled_qty)
                self._total_profit += profit
                logger.info(f"Grid fill: {level.side.value} @ {filled_price}, profit={profit:.4f}")
                self._place_counter_order(level)
                self._persist_state()
                for cb in self._callbacks:
                    cb("fill", level, profit)
                break

    def _place_counter_order(self, filled_level: GridLevel):
        if filled_level.side == GridSide.BUY:
            target_price = filled_level.price + self._step
            if target_price <= self.cfg.upper_price:
                new_level = GridLevel(price=round(target_price, 4), side=GridSide.SELL,
                                      size=self.cfg.order_size)
                self.levels.append(new_level)
                self._place_limit(new_level)
        else:
            target_price = filled_level.price - self._step
            if target_price >= self.cfg.lower_price:
                new_level = GridLevel(price=round(target_price, 4), side=GridSide.BUY,
                                      size=self.cfg.order_size)
                self.levels.append(new_level)
                self._place_limit(new_level)

    def _calculate_fill_profit(self, level: GridLevel, price: float, qty: float) -> float:
        if level.side == GridSide.SELL:
            return (price - level.price) * qty
        return 0.0

    def stop(self):
        self.active = False
        for level in self.levels:
            if level.order_id and not level.filled:
                try:
                    self.om.cancel_order(self.cfg.symbol, level.order_id)
                except Exception as e:
                    logger.error(f"Cancel error: {e}")
        logger.info("Grid stopped, orders cancelled")
        self._persist_state()

    def get_stats(self) -> dict:
        filled = sum(1 for l in self.levels if l.filled)
        return {
            "active": self.active,
            "levels_total": len(self.levels),
            "levels_filled": filled,
            "total_profit": round(self._total_profit, 6),
            "step": self._step,
        }

    def _persist_state(self):
        if self.state:
            self.state.save("grid_engine", {
                "config": self.cfg.__dict__,
                "levels": [(l.price, l.side.value, l.filled) for l in self.levels],
                "profit": self._total_profit,
                "active": self.active,
            })

    def add_callback(self, callback: Callable):
        self._callbacks.append(callback)
