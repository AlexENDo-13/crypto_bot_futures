#!/usr/bin/env python3
import math
from typing import Optional, Dict, Any
from src.core.trading.position import Position, OrderSide

class TradeExecutor:
    def __init__(self, settings, logger, order_manager, risk_manager, risk_controller):
        self.settings = settings; self.logger = logger; self.order_manager = order_manager
        self.risk_manager = risk_manager; self.risk_controller = risk_controller
        self.client = order_manager.client

    def _round_quantity(self, symbol, quantity, symbol_specs=None):
        step = float(symbol_specs.get("stepSize", 0.001)) if symbol_specs else 0.001
        if step <= 0: step = 0.001
        qty = math.floor(quantity / step) * step
        return max(qty, step)

    def _check_min_notional(self, quantity, price, symbol_specs=None):
        min_notional = float(symbol_specs.get("minNotional", 5.0)) if symbol_specs else 5.0
        return (quantity * price) >= min_notional

    async def execute_trade_async(self, candidate, balance, open_positions, trailing_enabled, trailing_distance, telegram, daily_pnl, weekly_pnl, start_balance):
        symbol = candidate.get("symbol"); indicators = candidate.get("indicators", {})
        direction = indicators.get("signal_direction", "NEUTRAL")
        current_price = indicators.get("close_price", 0.0); atr = indicators.get("atr_percent", 1.0)
        atr_value = indicators.get("atr", current_price * atr / 100)
        if not symbol or current_price <= 0 or direction == "NEUTRAL":
            self.logger.warning(f"⚠️ Невалидный кандидат: {symbol}, price={current_price}, dir={direction}"); return None
        side = OrderSide.BUY if direction == "LONG" else OrderSide.SELL
        bingx_symbol = symbol.replace("/", "-")
        symbol_specs = self.client.get_symbol_specs(bingx_symbol)
        if not symbol_specs:
            try:
                await self.client.get_symbol_info(bingx_symbol)
                symbol_specs = self.client.get_symbol_specs(bingx_symbol)
            except Exception as e: self.logger.warning(f"⚠️ Не удалось получить specs {symbol}: {e}"); symbol_specs = None
        leverage = int(self.settings.get("max_leverage", 3))
        if symbol_specs: leverage = min(leverage, symbol_specs.get("maxLeverage", leverage))
        stop_distance_pct = max(0.5, min(1.5 * atr, 10.0))
        risk_percent = float(self.settings.get("max_risk_per_trade", 1.0))
        quantity = self.risk_manager.calculate_position_size(symbol, balance, risk_percent, stop_distance_pct, leverage, atr_value, current_price, symbol_specs)
        if quantity is None or quantity <= 0:
            self.logger.warning(f"⚠️ {symbol}: qty=0 (balance={balance}, price={current_price})"); return None
        qty = self._round_quantity(symbol, quantity, symbol_specs)
        if qty <= 0: self.logger.warning(f"⚠️ {symbol}: qty после округления = 0"); return None
        if not self._check_min_notional(qty, current_price, symbol_specs):
            min_notional = float(symbol_specs.get("minNotional", 5.0)) if symbol_specs else 5.0
            qty = self._round_quantity(symbol, (min_notional * 1.05) / current_price, symbol_specs)
            if qty <= 0 or not self._check_min_notional(qty, current_price, symbol_specs):
                self.logger.warning(f"⚠️ {symbol}: не проходит мин. лот"); return None
        self.logger.info(f"🚀 Вход {side.value} {symbol} | Qty: {qty:.6f} | Цена: ~{current_price:.4f} | Плечо: {leverage}x")
        try: await self.client.set_leverage(bingx_symbol, leverage)
        except Exception as e: self.logger.warning(f"⚠️ Плечо {symbol}: {e}")
        try: await self.client.set_margin_mode(bingx_symbol, "CROSSED")
        except Exception as e: self.logger.warning(f"⚠️ Маржа {symbol}: {e}")
        try:
            temp_pos = Position(symbol=symbol, side=side, quantity=qty, entry_price=current_price, leverage=leverage)
            sl_price, tp_price = self.risk_manager.calculate_sl_tp(temp_pos, atr_value)
        except Exception as e: self.logger.error(f"❌ Ошибка SL/TP {symbol}: {e}"); return None
        order_side_str = "BUY" if side == OrderSide.BUY else "SELL"
        result = await self.client.place_order(symbol=bingx_symbol, side=order_side_str, quantity=qty, order_type="MARKET", position_side="BOTH")
        if result is None or result.get("error") or not result.get("orderId"):
            err = result.get("msg", "Unknown") if result else "No response"; code = result.get("code", -1) if result else -1
            self.logger.error(f"❌ Ордер отклонён {symbol}: [{code}] {err}"); return None
        avg_price = float(result.get("avgPrice", current_price))
        if avg_price <= 0: avg_price = current_price
        order_id = result.get("orderId", "")
        self.logger.info(f"✅ Ордер исполнен: {symbol} {side.value} | Qty: {qty:.6f} | Avg: {avg_price:.4f} | ID: {order_id}")
        sl_side = "SELL" if side == OrderSide.BUY else "BUY"
        sl_result = await self.client.place_stop_order(symbol=bingx_symbol, side=sl_side, stop_price=sl_price, order_type="STOP_MARKET", position_side="BOTH", close_position=True)
        sl_order_id = sl_result.get("orderId", "") if sl_result and not sl_result.get("error") else ""
        if sl_order_id: self.logger.info(f"🛡️ SL установлен: {symbol} @ {sl_price:.4f}")
        else: self.logger.warning(f"⚠️ SL не установлен {symbol}")
        tp_result = await self.client.place_stop_order(symbol=bingx_symbol, side=sl_side, stop_price=tp_price, order_type="TAKE_PROFIT_MARKET", position_side="BOTH", close_position=True)
        tp_order_id = tp_result.get("orderId", "") if tp_result and not tp_result.get("error") else ""
        if tp_order_id: self.logger.info(f"🎯 TP установлен: {symbol} @ {tp_price:.4f}")
        else: self.logger.warning(f"⚠️ TP не установлен {symbol}")
        try:
            pos = Position(symbol=symbol, side=side, quantity=qty, entry_price=avg_price, leverage=leverage,
                           stop_loss_price=sl_price, take_profit_price=tp_price, strategy=indicators.get("entry_type", "macd_rsi"),
                           order_id=order_id, sl_order_id=sl_order_id, tp_order_id=tp_order_id)
        except Exception as e: self.logger.error(f"❌ Ошибка создания позиции {symbol}: {e}"); return None
        self.risk_manager.register_position_open(pos)
        self.logger.log_trade(symbol=symbol, side=side.value, entry=avg_price, qty=qty, leverage=leverage, sl=sl_price, tp=tp_price)
        self.logger.info(f"✅ Позиция открыта: {symbol} {side.value} | Вход: {avg_price:.4f} | SL: {sl_price:.4f} | TP: {tp_price:.4f} | Qty: {qty:.6f} | Value: ${qty*avg_price:.2f} | Плечо: {leverage}x")
        if telegram:
            msg = f"🟢 **ОТКРЫТА ПОЗИЦИЯ** 🟢\nПара: {symbol}\nНаправление: **{side.value}**\nВход: {avg_price:.4f}\nПлечо: {leverage}x\nОбъём: {qty:.6f} (${qty*avg_price:.2f})\nSL: {sl_price:.4f} | TP: {tp_price:.4f}"
            try: telegram.send_sync(msg)
            except Exception: pass
        return pos

    async def close_position_async(self, symbol, side, quantity):
        bingx_symbol = symbol.replace("/", "-")
        close_side = "SELL" if side == OrderSide.BUY else "BUY"
        try:
            res = await self.client.place_order(symbol=bingx_symbol, side=close_side, quantity=quantity, order_type="MARKET", position_side="BOTH")
            if res and not res.get("error") and res.get("orderId"):
                self.logger.info(f"✅ Позиция {symbol} закрыта"); return True
            err = f"[{res.get('code')}] {res.get('msg')}" if res and res.get('error') else "No orderId"
            self.logger.error(f"❌ Ошибка закрытия {symbol}: {err}"); return False
        except Exception as e: self.logger.error(f"❌ Ошибка закрытия {symbol}: {e}"); return False
