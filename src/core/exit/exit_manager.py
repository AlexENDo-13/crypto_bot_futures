#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exit Manager — SL/TP, трейлинг-стоп, dead weight exit
"""
import logging
import datetime
from typing import Optional
from src.core.risk.risk_manager import Position
from src.config.settings import Settings

logger = logging.getLogger(__name__)


class ExitManager:
    """Менеджер выходов из позиций"""

    def __init__(self, settings: Settings):
        self.settings = settings

    def check_exit(self, position: Position, current_price: float) -> Optional[str]:
        """
        Проверить, нужно ли закрывать позицию.
        Возвращает причину выхода или None.
        """
        if current_price <= 0:
            return None

        # 1. Стоп-лосс
        if position.side == "LONG":
            if position.stop_loss > 0 and current_price <= position.stop_loss:
                return "STOP_LOSS"
        else:
            if position.stop_loss > 0 and current_price >= position.stop_loss:
                return "STOP_LOSS"

        # 2. Тейк-профит
        if position.side == "LONG":
            if position.take_profit > 0 and current_price >= position.take_profit:
                return "TAKE_PROFIT"
        else:
            if position.take_profit > 0 and current_price <= position.take_profit:
                return "TAKE_PROFIT"

        # 3. Трейлинг-стоп
        trailing_exit = self._check_trailing_stop(position, current_price)
        if trailing_exit:
            return trailing_exit

        # 4. Dead weight — позиция висит слишком долго без движения
        time_exit = self._check_time_exit(position)
        if time_exit:
            return time_exit

        return None

    def _check_trailing_stop(self, position: Position, current_price: float) -> Optional[str]:
        """Проверка трейлинг-стопа"""
        if not self.settings.get("trailing_stop_enabled", False):
            return None

        activation_pct = self.settings.get("trailing_activation", 1.5)
        callback_pct = self.settings.get("trailing_callback", 0.5)

        if position.side == "LONG":
            profit_pct = (current_price - position.entry_price) / position.entry_price * 100
            if profit_pct >= activation_pct:
                max_price = max(position.max_price_seen, current_price)
                position.max_price_seen = max_price
                callback_price = max_price * (1 - callback_pct / 100)
                if current_price <= callback_price:
                    return f"TRAILING_STOP (max={max_price:.2f})"
        else:
            profit_pct = (position.entry_price - current_price) / position.entry_price * 100
            if profit_pct >= activation_pct:
                min_price = min(position.min_price_seen, current_price)
                position.min_price_seen = min_price
                callback_price = min_price * (1 + callback_pct / 100)
                if current_price >= callback_price:
                    return f"TRAILING_STOP (min={min_price:.2f})"

        return None

    def _check_time_exit(self, position: Position) -> Optional[str]:
        """Проверка временного выхода (dead weight)"""
        max_hold = self.settings.get("max_hold_time_minutes")
        if not max_hold:
            return None
        if position.entry_time is None:
            return None
        hold_time = (datetime.datetime.utcnow() - position.entry_time).total_seconds() / 60
        if hold_time > max_hold:
            return f"TIME_EXIT ({hold_time:.0f}min)"
        return None

    def update_trailing(self, position: Position, current_price: float):
        """Обновление трейлинг-стопа (вызвать при каждом тике)"""
        if position.side == "LONG":
            position.max_price_seen = max(position.max_price_seen, current_price)
        else:
            position.min_price_seen = min(position.min_price_seen, current_price)
