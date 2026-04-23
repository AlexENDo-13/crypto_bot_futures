#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TradeExecutor — исправленный исполнитель торговых приказов.
Открытие позиции и установка SL/TP — отдельные операции.
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
    """Исполнитель торговых приказов."""

    def __init__(self, settings: Settings, logger: BotLogger, order_manager, risk_manager, risk_controller):
        self.settings = settings
        self.logger = logger
        self.order_manager = order_manager
        self.risk_manager = risk_manager
        self.risk_controller = risk_controller
        self.client = order_manager.client

    def _round_quantity(self, symbol: str, quantity: float, symbol_specs: dict = None) -> float:
        if symbol_specs:
            step = float(symbol_specs.get("stepSize", 0.001))
        else:
            step = 0.001
        if step <= 0:
            step = 0.001
        qty = math.floor(quantity / step) * step
        return max(qty, step)

    def _check_min_notional(self, quantity: float, price: float, symbol_specs: dict = None) -> bool:
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
            self.logger.warning(f"⚠️ Невалидный кандидат: symbol={symbol}, price={current_price}, dir={direction}")
            return None

        side = OrderSide.BUY if direction == "LONG" else OrderSide.SELL
        bingx_symbol = symbol.replace("/", "-")

        # Get symbol specs
        symbol_specs = self.client.get_symbol_specs(bingx_symbol)
        if not symbol_specs:
            try:
                await self.client.get_symbol_info(bingx_symbol)
                symbol_specs = self.client.get_symbol_specs(bingx_symbol)
            except Exception as e:
                self.logger.warning(f"⚠️ Не удалось получить specs {symbol}: {e}")
                symbol_specs = None

        # Determine leverage
        risk_percent = float(self.settings.get("max_risk_per_trade", 1.0))
        leverage = int(self.settings.get("max_leverage", 3))
        if symbol_specs:
            max_lev = symbol_specs.get("maxLeverage", leverage)
            leverage = min(leverage, max_lev)
            self.logger.info(f"📐 {symbol}: плечо {leverage}x (max={max_lev})")
        else:
            self.logger.warning(f"⚠️ {symbol}: symbol_specs не получены, используем плечо {leverage}x")

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

        if quantity is None or quantity <= 0:
            self.logger.warning(f"⚠️ {symbol}: Рассчитанный объём = 0 (balance={balance}, price={current_price})")
            return None

        qty = self._round_quantity(symbol, quantity, symbol_specs)
        if qty <= 0:
            self.logger.warning(f"⚠️ {symbol}: qty после округления = 0 (raw={quantity:.6f})")
            return None

        if not self._check_min_notional(qty, current_price, symbol_specs):
            min_notional = float(symbol_specs.get("minNotional", 5.0)) if symbol_specs else 5.0
            qty = self._round_quantity(symbol, (min_notional * 1.05) / current_price, symbol_specs)
            if qty <= 0 or not self._check_min_notional(qty, current_price, symbol_specs):
                self.logger.warning(f"⚠️ {symbol}: Не проходит минимальный лот ({min_notional} USDT)")
                return None

        self.logger.info(f"🚀 Попытка входа {side.value} по {symbol}. Объём: {qty:.6f}, Цена: ~{current_price:.4f}, Плечо: {leverage}x")

        # Set leverage
        try:
            await self.client.set_leverage(bingx_symbol, leverage)
        except Exception as e:
            self.logger.warning(f"⚠️ Не удалось установить плечо {symbol}: {e}")

        # Set margin mode
        try:
            await self.client.set_margin_mode(bingx_symbol, "CROSSED")
        except Exception as e:
            self.logger.warning(f"⚠️ Не удалось установить маржу {symbol}: {e}")

        # Calculate SL/TP
        try:
            temp_pos = Position(symbol=symbol, side=side, quantity=qty, entry_price=current_price, leverage=leverage)
            sl_price, tp_price = self.risk_manager.calculate_sl_tp(temp_pos, atr_value)
        except Exception as e:
            self.logger.error(f"❌ Ошибка расчёта SL/TP {symbol}: {e}")
            return None

        # Place MARKET order (clean, no SL/TP)
        order_side_str = "BUY" if side == OrderSide.BUY else "SELL"
        result = await self.client.place_order(
            symbol=bingx_symbol,
            side=order_side_str,
            quantity=qty,
            order_type="MARKET",
            position_side="BOTH",
        )

        if result is None:
            self.logger.error(f"❌ {symbol}: Нет ответа от биржи при размещении ордера (сеть/таймаут)")
            return None

        if result.get("error"):
            self.logger.error(f"❌ Биржа отклонила ордер {symbol}: [{result.get('code')}] {result.get('msg')}")
            return None

        if not result.get("orderId"):
            self.logger.error(f"❌ Биржа вернула ордер без orderId: {result}")
            return None

        avg_price = float(result.get("avgPrice", current_price))
        if avg_price <= 0:
            avg_price = current_price

        self.logger.info(f"✅ Ордер исполнен: {symbol} {side.value} | Qty: {qty:.6f} | Avg: {avg_price:.4f} | ID: {result.get('orderId')}")

        # Place SL order (STOP_MARKET, closePosition=true)
        sl_side = "SELL" if side == OrderSide.BUY else "BUY"
        sl_result = await self.client.place_stop_order(
            symbol=bingx_symbol,
            side=sl_side,
            stop_price=sl_price,
            order_type="STOP_MARKET",
            position_side="BOTH",
            close_position=True,
        )
        if sl_result and not sl_result.get("error"):
            self.logger.info(f"🛡️ SL установлен: {symbol} @ {sl_price:.4f}")
        else:
            err_msg = sl_result.get("msg", "Unknown") if sl_result else "No response"
            err_code = sl_result.get("code", -1) if sl_result else -1
            self.logger.warning(f"⚠️ Не удалось установить SL {symbol}: [{err_code}] {err_msg}")

        # Place TP order (TAKE_PROFIT_MARKET, closePosition=true)
        tp_result = await self.client.place_stop_order(
            symbol=bingx_symbol,
            side=sl_side,
            stop_price=tp_price,
            order_type="TAKE_PROFIT_MARKET",
            position_side="BOTH",
            close_position=True,
        )
        if tp_result and not tp_result.get("error"):
            self.logger.info(f"🎯 TP установлен: {symbol} @ {tp_price:.4f}")
        else:
            err_msg = tp_result.get("msg", "Unknown") if tp_result else "No response"
            err_code = tp_result.get("code", -1) if tp_result else -1
            self.logger.warning(f"⚠️ Не удалось установить TP {symbol}: [{err_code}] {err_msg}")

        # Create position object
        try:
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
        except Exception as e:
            self.logger.error(f"❌ Ошибка создания позиции {symbol}: {e}")
            return None

        self.risk_manager.register_position_open(pos)

        self.logger.info(
            f"✅ Позиция открыта: {symbol} {side.value} | "
            f"Вход: {avg_price:.4f} | SL: {sl_price:.4f} | TP: {tp_price:.4f} | "
            f"Qty: {qty:.6f} | Value: ${qty*avg_price:.2f} | Плечо: {leverage}x"
        )

        if telegram:
            msg = (
                f"🟢 **ОТКРЫТА ПОЗИЦИЯ** 🟢\n"
                f"Пара: {symbol}\n"
                f"Направление: **{side.value}**\n"
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
            if res and not res.get("error") and res.get("orderId"):
                self.logger.info(f"✅ Позиция {symbol} закрыта")
                return True
            err = f"[{res.get('code')}] {res.get('msg')}" if res and res.get('error') else "No orderId"
            self.logger.error(f"❌ Ошибка закрытия {symbol}: {err}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Ошибка закрытия {symbol}: {e}")
            return False
