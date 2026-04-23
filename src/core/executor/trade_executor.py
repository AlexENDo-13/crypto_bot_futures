#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import math
import time
from typing import Optional, Dict, Any, List

from src.config.settings import Settings
from src.core.logger import BotLogger
from src.core.trading.position import Position
from src.config.constants import OrderSide

logger = logging.getLogger(__name__)

class TradeExecutor:
    """
    Исполнитель торговых приказов.
    Отвечает за открытие позиций, расчет размера лота и начальные стопы.
    """
    MIN_NOTIONAL = 5.0  # минимальная стоимость позиции в USDT на BingX Futures

    def __init__(self, settings: Settings, logger: BotLogger, order_manager, risk_manager, risk_controller):
        self.settings = settings
        self.logger = logger
        self.order_manager = order_manager
        self.risk_manager = risk_manager
        self.risk_controller = risk_controller
        self.client = order_manager.client

    def _round_quantity(self, symbol: str, quantity: float) -> float:
        """Округляет количество монеты до допустимого шага (stepSize)."""
        step = 0.001 # Базовый шаг, если нет информации с биржи
        qty = math.floor(quantity / step) * step
        return max(qty, step)

    def _check_min_notional(self, quantity: float, price: float) -> bool:
        """Проверяет, что стоимость позиции >= MIN_NOTIONAL (5 USDT)."""
        return (quantity * price) >= self.MIN_NOTIONAL

    async def execute_trade_async(
        self,
        candidate: Dict,
        balance: float,
        open_positions: Dict[str, Position],
        trailing_enabled: bool,
        trailing_distance: float,
        telegram,
        daily_pnl: float,
        weekly_pnl: float,
        start_balance: float
    ) -> Optional[Position]:
        """
        Асинхронная попытка открыть сделку на основе кандидата от сканера.
        """
        symbol = candidate.get('symbol')
        indicators = candidate.get('indicators', {})
        direction = indicators.get('signal_direction', 'NEUTRAL')
        current_price = indicators.get('close_price', 0.0)
        atr = indicators.get('atr_percent', 1.0)

        if not symbol or current_price <= 0 or direction == 'NEUTRAL':
            return None

        # Определяем сторону
        side = OrderSide.BUY if direction == 'LONG' else OrderSide.SELL

        # Расчет риска и размера позиции
        risk_percent = self.settings.get("max_risk_per_trade", 1.0)
        leverage = self.settings.get("max_leverage", 3)
        stop_distance_pct = max(1.0, min(1.5 * atr, 10.0))

        quantity = self.risk_manager.calculate_position_size(
            symbol=symbol,
            balance=balance,
            risk_percent=risk_percent,
            stop_distance_pct=stop_distance_pct,
            leverage=leverage,
            atr=atr,
            current_price=current_price
        )

        if quantity <= 0:
            self.logger.warning(f"⚠️ {symbol}: Рассчитанный объем равен 0")
            return None

        # Округление и проверка минимального объема (5 USDT)
        qty = self._round_quantity(symbol, quantity)
        if not self._check_min_notional(qty, current_price):
            qty = self._round_quantity(symbol, (self.MIN_NOTIONAL * 1.05) / current_price)
            if not self._check_min_notional(qty, current_price):
                self.logger.warning(f"⚠️ {symbol}: Не проходит минимальный лот BingX (5 USDT). Пропуск.")
                return None

        self.logger.info(f"🚀 Попытка входа {side.value} по {symbol}. Объем: {qty}, Цена: ~{current_price}")

        # Отправляем ордер через order_manager
        order_side_str = "BUY" if side == OrderSide.BUY else "SELL"
        
        # Для асинхронного вызова (если order_manager использует AsyncBingXClient)
        try:
            result = await self.order_manager.client.place_order(
                symbol=symbol.replace('/', '-'),
                side=order_side_str,
                quantity=qty,
                leverage=leverage,
                order_type="MARKET"
            )
        except Exception as e:
            self.logger.error(f"❌ Ошибка отправки ордера {symbol}: {e}")
            return None

        # Если ордер не прошел
        if not result or not result.get("orderId"):
            self.logger.error(f"❌ Биржа отклонила ордер по {symbol}: {result}")
            return None

        avg_price = float(result.get("avgPrice", current_price))
        if avg_price <= 0:
            avg_price = current_price

        # Создаем объект позиции
        pos = Position(
            symbol=symbol,
            side=side,
            quantity=qty,
            entry_price=avg_price,
            leverage=leverage,
            stop_loss_price=0.0,
            take_profit_price=0.0
        )

        # Выставляем начальные стопы
        sl_price, tp_price = self.risk_manager.calculate_sl_tp(pos, atr)
        pos.stop_loss_price = sl_price
        pos.take_profit_price = tp_price

        self.logger.info(f"✅ Успешный вход: {symbol} {side.value} | Цена: {avg_price:.4f} | SL: {sl_price:.4f} | TP: {tp_price:.4f}")

        if telegram:
            msg = (
                f"🟢 <b>ОТКРЫТА ПОЗИЦИЯ</b> 🟢\n"
                f"Пара: {symbol}\n"
                f"Направление: <b>{side.value}</b> 📈\n"
                f"Вход: {avg_price:.4f}\n"
                f"Плечо: {leverage}x\n"
                f"SL: {sl_price:.4f} | TP: {tp_price:.4f}\n"
            )
            telegram.send_sync(msg)

        return pos

    async def close_position_async(self, symbol: str, side: OrderSide, quantity: float) -> bool:
        """Асинхронно закрывает позицию на бирже."""
        order_side_str = "SELL" if side == OrderSide.BUY else "BUY" # Обратный ордер
        try:
            res = await self.order_manager.client.place_order(
                symbol=symbol.replace('/', '-'),
                side=order_side_str,
                quantity=quantity,
                leverage=1, # Плечо при закрытии не важно
                order_type="MARKET"
            )
            if res and res.get("orderId"):
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка закрытия {symbol}: {e}")
            return False
