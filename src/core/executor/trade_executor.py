"""
TradeExecutor v11.2 - FIXED: quantity rounding, close position side logic
"""
import math
from typing import Optional, Dict, Any
from src.core.trading.position import Position, OrderSide


class TradeExecutor:
    def __init__(self, settings, logger, order_manager, risk_manager, risk_controller):
        self.settings = settings
        self.logger = logger
        self.order_manager = order_manager
        self.risk_manager = risk_manager
        self.risk_controller = risk_controller
        self.client = order_manager.client

    def _round_quantity(self, symbol, quantity, symbol_specs=None):
        if symbol_specs:
            step = float(symbol_specs.get("size", symbol_specs.get("stepSize", 0.001)))
        else:
            step = 0.001
        if step <= 0:
            step = 0.001
        qty = math.floor(quantity / step) * step
        return max(qty, step)

    def _check_min_notional(self, quantity, price, symbol_specs=None):
        if symbol_specs:
            min_notional = float(symbol_specs.get("tradeMinUSDT", symbol_specs.get("minNotional", 5.0)))
        else:
            min_notional = 5.0
        return (quantity * price) >= min_notional

    async def execute_trade_async(self, candidate, balance, open_positions, trailing_enabled,
                                  trailing_distance, telegram, daily_pnl, weekly_pnl, start_balance):
        symbol = candidate.get("symbol")
        indicators = candidate.get("indicators", {})
        direction = indicators.get("signal_direction", "NEUTRAL")
        current_price = indicators.get("close_price", 0.0)
        atr = indicators.get("atr", current_price * 0.01)
        atr_pct = indicators.get("atr_percent", 1.0)

        if not symbol or current_price <= 0 or direction == "NEUTRAL":
            self.logger.warning(f"Invalid candidate: {symbol}, price={current_price}, dir={direction}")
            return None

        side = OrderSide.BUY if direction == "LONG" else OrderSide.SELL
        position_side = "LONG" if side == OrderSide.BUY else "SHORT"
        bingx_symbol = symbol.replace("/", "-")

        symbol_specs = self.client.get_symbol_specs(bingx_symbol)
        if not symbol_specs:
            try:
                await self.client.get_symbol_info()
                symbol_specs = self.client.get_symbol_specs(bingx_symbol)
            except Exception as e:
                self.logger.warning(f"Could not get specs for {symbol}: {e}")

        leverage = int(self.settings.get("max_leverage", 3))
        if symbol_specs:
            leverage = min(leverage, symbol_specs.get("maxLeverage", leverage))

        stop_distance_pct = max(0.3, min(1.5 * atr_pct, 10.0))
        risk_percent = float(self.settings.get("max_risk_per_trade", 1.0))

        quantity = self.risk_manager.calculate_position_size(
            symbol, balance, risk_percent, stop_distance_pct, leverage, atr, current_price, symbol_specs
        )
        if quantity is None or quantity <= 0:
            self.logger.warning(f"{symbol}: qty=0 (balance={balance}, price={current_price})")
            return None

        qty = self._round_quantity(symbol, quantity, symbol_specs)
        if qty <= 0:
            self.logger.warning(f"{symbol}: qty after rounding = 0")
            return None

        if not self._check_min_notional(qty, current_price, symbol_specs):
            min_n = float(symbol_specs.get("tradeMinUSDT", symbol_specs.get("minNotional", 5.0))) if symbol_specs else 5.0
            qty = self._round_quantity(symbol, (min_n * 1.05) / current_price, symbol_specs)
            if qty <= 0 or not self._check_min_notional(qty, current_price, symbol_specs):
                self.logger.warning(f"{symbol}: below min notional")
                return None

        self.logger.info(f"ENTRY PREPARE {side.value} {symbol} | Qty: {qty:.6f} | Price: ~{current_price:.4f} | "
                         f"Leverage: {leverage}x | PositionSide: {position_side} | StopDist: {stop_distance_pct:.2f}%")

        try:
            lev_res = await self.client.set_leverage(bingx_symbol, leverage, side=position_side)
            if lev_res and lev_res.get("error"):
                self.logger.warning(f"Leverage warning {symbol}: {lev_res.get('msg')} (may already be set)")
        except Exception as e:
            self.logger.warning(f"Leverage error {symbol}: {e} (continuing)")

        try:
            margin_res = await self.client.set_margin_mode(bingx_symbol, "CROSSED")
            if margin_res and margin_res.get("code") == 0:
                self.logger.info(f"Margin mode set: {bingx_symbol} CROSSED")
        except Exception as e:
            self.logger.debug(f"Margin mode error {symbol}: {e} (ignoring)")

        try:
            temp_pos = Position(symbol=symbol, side=side, quantity=qty, entry_price=current_price, leverage=leverage)
            sl_price, tp_price = self.risk_manager.calculate_sl_tp(temp_pos, atr)
        except Exception as e:
            self.logger.error(f"SL/TP error {symbol}: {e}")
            return None

        order_side_str = "BUY" if side == OrderSide.BUY else "SELL"
        self.logger.info(f"PLACING ORDER: {bingx_symbol} {order_side_str} {position_side} qty={qty:.6f} MARKET")
        result = await self.client.place_order(
            symbol=bingx_symbol, side=order_side_str, position_side=position_side,
            quantity=qty, order_type="MARKET"
        )
        # Проверяем ответ
        if result is None or result.get("error") or not result.get("orderId"):
            err = result.get("msg", "Unknown") if result else "No response"
            code = result.get("code", -1) if result else -1
            self.logger.error(f"ORDER REJECTED {symbol}: [{code}] {err}")
            return None

        avg_price = float(result.get("avgPrice", result.get("avg_price", current_price)))
        if avg_price <= 0:
            avg_price = current_price
        order_id = result.get("orderId", "")
        self.logger.info(f"ORDER EXECUTED: {symbol} {side.value} | Qty: {qty:.6f} | Avg: {avg_price:.4f} | ID: {order_id}")

        sl_side = "SELL" if side == OrderSide.BUY else "BUY"
        sl_result = await self.client.place_stop_order(
            symbol=bingx_symbol, side=sl_side, stop_price=sl_price,
            order_type="STOP_MARKET", position_side=position_side, close_position=True
        )
        sl_order_id = sl_result.get("orderId", "") if sl_result and not sl_result.get("error") else ""
        if sl_order_id:
            self.logger.info(f"SL SET: {symbol} @ {sl_price:.4f} | ID: {sl_order_id}")
        else:
            self.logger.warning(f"SL NOT SET {symbol}: {sl_result.get('msg', 'unknown error')}")

        tp_result = await self.client.place_stop_order(
            symbol=bingx_symbol, side=sl_side, stop_price=tp_price,
            order_type="TAKE_PROFIT_MARKET", position_side=position_side, close_position=True
        )
        tp_order_id = tp_result.get("orderId", "") if tp_result and not tp_result.get("error") else ""
        if tp_order_id:
            self.logger.info(f"TP SET: {symbol} @ {tp_price:.4f} | ID: {tp_order_id}")
        else:
            self.logger.warning(f"TP NOT SET {symbol}: {tp_result.get('msg', 'unknown error')}")

        try:
            pos = Position(
                symbol=symbol, side=side, quantity=qty, entry_price=avg_price, leverage=leverage,
                stop_loss_price=sl_price, take_profit_price=tp_price,
                strategy=indicators.get("entry_type", "mixed"),
                order_id=order_id, sl_order_id=sl_order_id, tp_order_id=tp_order_id
            )
        except Exception as e:
            self.logger.error(f"Position creation error {symbol}: {e}")
            return None

        self.risk_manager.register_position_open(pos)
        self.logger.info(f"POSITION OPENED: {symbol} {side.value} | Entry: {avg_price:.4f} | "
                         f"SL: {sl_price:.4f} | TP: {tp_price:.4f} | Qty: {qty:.6f} | "
                         f"Value: ${qty*avg_price:.2f} | Leverage: {leverage}x")
        return pos

    async def close_position_async(self, symbol, side, quantity, position_side="LONG"):
        """
        Закрывает позицию. side - OrderSide позиции.
        position_side игнорируется, определяется автоматически.
        """
        bingx_symbol = symbol.replace("/", "-")
        # Определяем сторону закрытия
        if side == OrderSide.BUY:
            close_side = "SELL"
            actual_position_side = "LONG"
        else:
            close_side = "BUY"
            actual_position_side = "SHORT"

        try:
            # Сначала пытаемся закрыть через close_position (передаём 0 для полного закрытия)
            res = await self.client.close_position(
                symbol=bingx_symbol, position_side=actual_position_side, quantity="0"
            )
            if res and not res.get("error") and res.get("orderId"):
                self.logger.info(f"Position {symbol} closed via close_position API | ID: {res.get('orderId')}")
                return True
            # Fallback: рыночный ордер на конкретное количество
            res = await self.client.place_order(
                symbol=bingx_symbol, side=close_side, position_side=actual_position_side,
                quantity=quantity, order_type="MARKET"
            )
            if res and not res.get("error") and res.get("orderId"):
                self.logger.info(f"Position {symbol} closed via market order | ID: {res.get('orderId')}")
                return True
            err = f"[{res.get('code')}] {res.get('msg')}" if res and res.get("error") else "No orderId"
            self.logger.error(f"Close error {symbol}: {err}")
            return False
        except Exception as e:
            self.logger.error(f"Close error {symbol}: {e}")
            return False
