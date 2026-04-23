#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TradeExecutor — полноценный исполнитель торговых приказов.
Корректный расчёт qty, обработка minNotional, установка плеча и маржи.
"""
import logging
import math
import time
from typing import Optional, Dict, Any

from src.config.settings import Settings
from src.core.logger import BotLogger
from src.core.trading.position import Position, OrderSide

logger = logging.getLogger(__name__)


class TradeExecutor:
    """Исполнитель торговых приказов с адаптивным расчётом позиций."""

    def __init__(self, settings: Settings, logger: BotLogger, order_manager, risk_manager, risk_controller):
        self.settings = settings
        self.logger = logger
        self.order_manager = order_manager
        self.risk_manager = risk_manager
        self.risk_controller = risk_controller
        self.client = order_manager.client

    def _round_quantity(self, symbol: str, quantity: float, symbol_specs: dict = None) -> float:
        """Округляет количество до допустимого шага."""
        if symbol_specs:
            step = float(symbol_specs.get("stepSize", 0.001))
        else:
            step = 0.001

        if step <= 0:
            step = 0.001

        qty = math.floor(quantity / step) * step
        return max(qty, step)

    def _check_min_notional(self, quantity: float, price: float, symbol_specs: dict = None) -> bool:
        """Проверяет минимальную стоимость позиции."""
        if symbol_specs:
            min_notional = float(symbol_specs.get("minNotional", 5.0))
        else:
            min_notional = 5.0
        return (quantity * price) >= min_notional

    async def execute_trade_async(
        self,
        candidate: Dict[str, Any],
        balance: float,
        open_positions: Dict[str, Position],
        trailing_enabled: bool,
        trailing_distance: float,
        telegram,
        daily_pnl: float,
        weekly_pnl: float,
        start_balance: float,
    ) -> Optional[Position]:
        """Асинхронная попытка открыть сделку."""
        symbol = candidate.get("symbol")
        indicators = candidate.get("indicators", {})
        direction = indicators.get("signal_direction", "NEUTRAL")
        current_price = indicators.get("close_price", 0.0)
        atr = indicators.get("atr_percent", 1.0)
        atr_value = indicators.get("atr", current_price * atr / 100)

        if not symbol or current_price <= 0 or direction == "NEUTRAL":
            return None

        # Determine side
        side = OrderSide.BUY if direction == "LONG" else OrderSide.SELL

        # Get symbol specs from exchange
        symbol_specs = self.client.get_symbol_specs(symbol.replace("/", "-"))
        if not symbol_specs:
            # Try to fetch if not cached
            try:
                await self.client.get_symbol_info(symbol.replace("/", "-"))
                symbol_specs = self.client.get_symbol_specs(symbol.replace("/", "-"))
            except Exception:
                pass

        # Risk and position sizing
        risk_percent = float(self.settings.get("max_risk_per_trade", 1.0))
        leverage = int(self.settings.get("max_leverage", 3))
        if symbol_specs:
            max_lev = symbol_specs.get("maxLeverage", leverage)
            leverage = min(leverage, max_lev)

        stop_distance_pct = max(0.5, min(1.5 * atr, 10.0))

        quantity = self.risk_manager.calculate_position_size(
            symbol=symbol,
            balance=balance,
            risk_percent=risk_percent,
            stop_distance_pct=stop_distance_pct,
            leverage=leverage,
            atr=atr_value,
            current_price=current_price,
            symbol_specs=symbol_specs,
        )

        if quantity <= 0:
            self.logger.warning(f"⚠️ {symbol}: Рассчитанный объём равен 0")
            return None

        # Round and check minimum
        qty = self._round_quantity(symbol, quantity, symbol_specs)
        if not self._check_min_notional(qty, current_price, symbol_specs):
            # Try to increase to minimum
            min_notional = float(symbol_specs.get("minNotional", 5.0)) if symbol_specs else 5.0
            qty = self._round_quantity(symbol, (min_notional * 1.05) / current_price, symbol_specs)
            if not self._check_min_notional(qty, current_price, symbol_specs):
                self.logger.warning(f"⚠️ {symbol}: Не проходит минимальный лот ({min_notional} USDT). Пропуск.")
                return None

        self.logger.info(f"🚀 Попытка входа {side.value} по {symbol}. Объём: {qty:.6f}, Цена: ~{current_price:.4f}")

        # Set leverage first
        bingx_symbol = symbol.replace("/", "-")
        try:
            await self.client.set_leverage(bingx_symbol, leverage)
        except Exception as e:
            self.logger.warning(f"⚠️ Не удалось установить плечо {symbol}: {e}")

        # Set margin mode
        try:
            await self.client.set_margin_mode(bingx_symbol, "CROSSED")
        except Exception as e:
            self.logger.warning(f"⚠️ Не удалось установить маржу {symbol}: {e}")

        # Calculate SL/TP before placing order
        temp_pos = Position(
            symbol=symbol, side=side, quantity=qty,
            entry_price=current_price, leverage=leverage
        )
        sl_price, tp_price = self.risk_manager.calculate_sl_tp(temp_pos, atr_value)

        # Place order
        order_side_str = "BUY" if side == OrderSide.BUY else "SELL"
        try:
            result = await self.client.place_order(
                symbol=bingx_symbol,
                side=order_side_str,
                quantity=qty,
                leverage=leverage,
                order_type="MARKET",
                position_side="BOTH",
                stop_loss=sl_price,
                take_profit=tp_price,
            )
        except Exception as e:
            self.logger.error(f"❌ Ошибка отправки ордера {symbol}: {e}")
            return None

        if not result or not result.get("orderId"):
            self.logger.error(f"❌ Биржа отклонила ордер по {symbol}: {result}")
            return None

        avg_price = float(result.get("avgPrice", current_price))
        if avg_price <= 0:
            avg_price = current_price

        # Create position object
        pos = Position(
            symbol=symbol,
            side=side,
            quantity=qty,
            entry_price=avg_price,
            leverage=leverage,
            stop_loss_price=sl_price,
            take_profit_price=tp_price,
            strategy=indicators.get("entry_type", "macd_rsi"),
        )

        self.risk_manager.register_position_open(pos)

        self.logger.info(
            f"✅ Успешный вход: {symbol} {side.value} | "
            f"Цена: {avg_price:.4f} | SL: {sl_price:.4f} | TP: {tp_price:.4f} | "
            f"Qty: {qty:.6f} | Value: ${qty*avg_price:.2f}"
        )

        if telegram:
            msg = (
                f"🟢 **ОТКРЫТА ПОЗИЦИЯ** 🟢\n"
                f"Пара: {symbol}\n"
                f"Направление: **{side.value}** 📈\n"
                f"Вход: {avg_price:.4f}\n"
                f"Плечо: {leverage}x\n"
                f"Объём: {qty:.6f} (${qty*avg_price:.2f})\n"
                f"SL: {sl_price:.4f} | TP: {tp_price:.4f}\n"
                f"Риск: {self.risk_manager.risk_per_trade:.1f}%"
            )
            try:
                telegram.send_sync(msg)
            except Exception:
                pass

        return pos

    async def close_position_async(self, symbol: str, side: OrderSide, quantity: float) -> bool:
        """Асинхронно закрывает позицию."""
        bingx_symbol = symbol.replace("/", "-")
        order_side_str = "SELL" if side == OrderSide.BUY else "BUY"
        try:
            res = await self.client.place_order(
                symbol=bingx_symbol,
                side=order_side_str,
                quantity=quantity,
                order_type="MARKET",
                position_side="BOTH",
            )
            if res and res.get("orderId"):
                self.logger.info(f"✅ Позиция {symbol} закрыта")
                return True
            return False
        except Exception as e:
            self.logger.error(f"❌ Ошибка закрытия {symbol}: {e}")
            return False
