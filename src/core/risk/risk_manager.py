#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RiskManager — полноценный менеджер рисков.
Расчёт размера позиции, SL/TP, анти-погоня, защита от просадок.
"""
import logging
import math
import time
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

from src.core.trading.position import Position, OrderSide, ExitReason

logger = logging.getLogger("RiskManager")


class AntiChase:
    """Защита от погони за рынком — ограничение частоты сделок."""

    def __init__(self, max_orders_per_hour: int = 6, cooldown_seconds: float = 300):
        self.max_orders_per_hour = max_orders_per_hour
        self.cooldown_seconds = cooldown_seconds
        self._trade_times: list = []
        self._last_trade_time: float = 0

    def can_trade(self) -> Tuple[bool, str]:
        """Проверяет, можно ли открыть новую сделку."""
        now = time.time()

        # Cooldown check
        if now - self._last_trade_time < self.cooldown_seconds:
            remaining = self.cooldown_seconds - (now - self._last_trade_time)
            return False, f"Cooldown: {remaining:.0f}s remaining"

        # Hourly limit check
        hour_ago = now - 3600
        self._trade_times = [t for t in self._trade_times if t > hour_ago]
        if len(self._trade_times) >= self.max_orders_per_hour:
            return False, f"Hourly limit reached ({self.max_orders_per_hour})"

        return True, "OK"

    def register_trade(self):
        """Регистрирует новую сделку."""
        now = time.time()
        self._trade_times.append(now)
        self._last_trade_time = now


class RiskManager:
    """Полноценный менеджер рисков с адаптивным расчётом позиций."""

    def __init__(self, client, settings: dict):
        self.client = client
        self.settings = settings
        self.logger = logger
        self._cached_balance = 0.0
        self._balance_cache_time = 0
        self._balance_cache_ttl = 30  # 30 seconds

        # Risk parameters
        self.max_positions = int(settings.get("max_positions", 3))
        self.risk_per_trade = float(settings.get("max_risk_per_trade", 1.0))
        self.max_total_risk = float(settings.get("max_total_risk_percent", 5.0))
        self.max_leverage = int(settings.get("max_leverage", 10))
        self.default_sl_pct = float(settings.get("default_sl_pct", 1.5))
        self.default_tp_pct = float(settings.get("default_tp_pct", 3.0))
        self.daily_loss_limit = float(settings.get("daily_loss_limit_percent", 8.0))
        self.anti_chase_threshold = float(settings.get("anti_chase_threshold_percent", 0.3))
        self.trailing_enabled = settings.get("trailing_stop_enabled", True)
        self.trailing_distance = float(settings.get("trailing_stop_distance_percent", 2.0))
        self.trailing_activation = float(settings.get("trailing_activation", 1.5))
        self.trailing_callback = float(settings.get("trailing_callback", 0.5))
        self.max_hold_time = float(settings.get("max_hold_time_minutes", 240))
        self.anti_martingale = settings.get("anti_martingale_enabled", True)
        self.anti_martingale_reduction = float(settings.get("anti_martingale_risk_reduction", 0.8))
        self.weekend_risk_multiplier = float(settings.get("weekend_risk_multiplier", 0.5))
        self.reduce_weekend = settings.get("reduce_risk_on_weekends", True)

        # State tracking
        self.anti_chase = AntiChase(
            max_orders_per_hour=int(settings.get("max_orders_per_hour", 6)),
            cooldown_seconds=300
        )
        self.daily_pnl = 0.0
        self.daily_loss = 0.0
        self.consecutive_losses = 0
        self.total_risk_exposure = 0.0
        self._daily_reset_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    def _reset_daily_if_needed(self):
        """Сбрасывает дневную статистику при смене дня."""
        now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        if now > self._daily_reset_time:
            self.daily_pnl = 0.0
            self.daily_loss = 0.0
            self.consecutive_losses = 0
            self.total_risk_exposure = 0.0
            self._daily_reset_time = now
            self.logger.info("Дневная статистика рисков сброшена")

    async def get_account_balance(self) -> Dict[str, float]:
        """Получает баланс с кэшированием."""
        now = time.time()
        if now - self._balance_cache_time < self._balance_cache_ttl and self._cached_balance > 0:
            return {"total_equity": self._cached_balance, "available_balance": self._cached_balance}

        try:
            account = await self.client.get_account_info()
            if account and "balance" in account:
                balance = float(account["balance"])
                self._cached_balance = balance
                self._balance_cache_time = now
                return {"total_equity": balance, "available_balance": balance}
        except Exception as e:
            self.logger.error(f"Ошибка получения баланса: {e}")

        return {"total_equity": self._cached_balance, "available_balance": self._cached_balance}

    def calculate_position_size(
        self,
        symbol: str,
        balance: float,
        risk_percent: float,
        stop_distance_pct: float,
        leverage: int,
        atr: float,
        current_price: float,
        symbol_specs: dict = None,
    ) -> float:
        """
        Адаптивный расчёт размера позиции.
        Подстраивается под любой депозит (даже $10-50).
        """
        self._reset_daily_if_needed()

        if balance <= 0 or current_price <= 0:
            return 0.0

        # Apply weekend reduction
        is_weekend = datetime.utcnow().weekday() >= 5
        if is_weekend and self.reduce_weekend:
            risk_percent *= self.weekend_risk_multiplier
            leverage = max(1, int(leverage * self.weekend_risk_multiplier))

        # Anti-martingale: reduce risk after losses
        if self.consecutive_losses > 0 and self.anti_martingale:
            reduction = self.anti_martingale_reduction ** self.consecutive_losses
            risk_percent *= reduction
            self.logger.info(f"Anti-martingale: риск снижен на {reduction*100:.0f}% (поражений подряд: {self.consecutive_losses})")

        # Ensure minimum risk for small balances
        risk_percent = max(0.1, min(risk_percent, 5.0))

        # Calculate risk amount in USDT
        risk_amount = balance * (risk_percent / 100)

        # Minimum risk amount ($0.50 for micro accounts)
        min_risk = 0.5
        risk_amount = max(risk_amount, min_risk)

        # Stop distance sanity check
        stop_distance_pct = max(0.3, min(stop_distance_pct, 10.0))

        # Calculate position value needed for this risk
        position_value = risk_amount / (stop_distance_pct / 100)

        # Apply leverage
        margin_required = position_value / leverage

        # Don't use more than 50% of balance as margin
        max_margin = balance * 0.5
        if margin_required > max_margin:
            margin_required = max_margin
            position_value = margin_required * leverage

        # Calculate quantity
        quantity = position_value / current_price

        # Apply symbol constraints
        if symbol_specs:
            step_size = float(symbol_specs.get("stepSize", 0.001))
            min_notional = float(symbol_specs.get("minNotional", 5.0))

            # Round to step size
            quantity = math.floor(quantity / step_size) * step_size

            # Ensure minimum notional
            if quantity * current_price < min_notional:
                quantity = math.ceil(min_notional / current_price / step_size) * step_size
        else:
            # Default rounding
            quantity = math.floor(quantity / 0.001) * 0.001
            if quantity * current_price < 5.0:
                quantity = math.ceil(5.0 / current_price / 0.001) * 0.001

        # Final sanity checks
        if quantity <= 0:
            return 0.0

        # Check total risk exposure
        total_risk_pct = (self.total_risk_exposure + risk_amount) / balance * 100
        if total_risk_pct > self.max_total_risk:
            self.logger.warning(f"Превышен общий риск ({total_risk_pct:.1f}% > {self.max_total_risk}%)")
            return 0.0

        self.logger.info(
            f"Расчёт позиции {symbol}: qty={quantity:.6f}, "
            f"value=${quantity*current_price:.2f}, margin=${margin_required:.2f}, "
            f"risk={risk_amount:.2f} USDT ({risk_percent:.2f}%), leverage={leverage}x"
        )

        return quantity

    def calculate_sl_tp(self, position: Position, atr: float = None) -> Tuple[float, float]:
        """Рассчитывает стоп-лосс и тейк-профит."""
        if atr is None:
            atr = position.entry_price * (self.default_sl_pct / 100)

        atr_multiplier_sl = 1.5
        atr_multiplier_tp = 3.0

        if position.side == OrderSide.BUY:
            sl_price = position.entry_price - (atr * atr_multiplier_sl)
            tp_price = position.entry_price + (atr * atr_multiplier_tp)
        else:
            sl_price = position.entry_price + (atr * atr_multiplier_sl)
            tp_price = position.entry_price - (atr * atr_multiplier_tp)

        # Ensure minimum distances
        min_sl_dist = position.entry_price * (self.default_sl_pct / 100)
        min_tp_dist = position.entry_price * (self.default_tp_pct / 100)

        if position.side == OrderSide.BUY:
            sl_price = min(sl_price, position.entry_price - min_sl_dist)
            tp_price = max(tp_price, position.entry_price + min_tp_dist)
        else:
            sl_price = max(sl_price, position.entry_price + min_sl_dist)
            tp_price = min(tp_price, position.entry_price - min_tp_dist)

        return round(sl_price, 4), round(tp_price, 4)

    def update_pnl(self, pnl: float):
        """Обновляет PnL и отслеживает серии."""
        self._reset_daily_if_needed()
        self.daily_pnl += pnl
        if pnl < 0:
            self.daily_loss += abs(pnl)
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def check_circuit_breaker(self, balance: float) -> Tuple[bool, str]:
        """Проверяет, не пора ли остановиться."""
        self._reset_daily_if_needed()

        # Daily loss limit
        if balance > 0:
            daily_loss_pct = (self.daily_loss / balance) * 100
            if daily_loss_pct >= self.daily_loss_limit:
                return False, f"Дневной лимит убытков достигнут ({daily_loss_pct:.1f}%)"

        # Consecutive losses
        if self.consecutive_losses >= 5:
            return False, f"Слишком много убытков подряд ({self.consecutive_losses})"

        return True, "OK"

    def can_open_position(self, current_positions_count: int, balance: float) -> Tuple[bool, str]:
        """Проверяет, можно ли открыть новую позицию."""
        self._reset_daily_if_needed()

        if current_positions_count >= self.max_positions:
            return False, f"Лимит позиций ({self.max_positions})"

        ok, reason = self.check_circuit_breaker(balance)
        if not ok:
            return False, reason

        ok, reason = self.anti_chase.can_trade()
        if not ok:
            return False, reason

        return True, "OK"

    def register_position_open(self, position: Position):
        """Регистрирует открытие позиции."""
        self.anti_chase.register_trade()
        if position.stop_loss_price and position.entry_price > 0:
            sl_distance = abs(position.entry_price - position.stop_loss_price) / position.entry_price
            risk = position.quantity * position.entry_price * sl_distance
            self.total_risk_exposure += risk

    def register_position_close(self, position: Position):
        """Регистрирует закрытие позиции."""
        if position.stop_loss_price and position.entry_price > 0:
            sl_distance = abs(position.entry_price - position.stop_loss_price) / position.entry_price
            risk = position.quantity * position.entry_price * sl_distance
            self.total_risk_exposure = max(0, self.total_risk_exposure - risk)

    def get_daily_stats(self) -> dict:
        """Возвращает дневную статистику."""
        self._reset_daily_if_needed()
        return {
            "daily_pnl": self.daily_pnl,
            "daily_loss": self.daily_loss,
            "consecutive_losses": self.consecutive_losses,
            "total_risk_exposure": self.total_risk_exposure,
            "max_positions": self.max_positions,
        }
