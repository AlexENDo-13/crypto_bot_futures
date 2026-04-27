#!/usr/bin/env python3
"""TradeExecutor v11 — Fixed: better order validation, quantity handling, clearer logs."""
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

        # Get symbol specs
        symbol_specs = self.client.get_symbol_specs(bingx_symbol)
        if not symbol_specs:
            try:
                await self.client.get_symbol_info()
                symbol_specs = self.client.get_symbol_specs(bingx_symbol)
            except Exception as e:
                self.logger.warning(f"Could not get specs for {symbol}: {e}")
                symbol_specs = None

        leverage = int(self.settings.get("max_leverage", 3))
        if symbol_specs:
            leverage = min(leverage, symbol_specs.get("maxLeverage", leverage))

        # Adaptive stop distance
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
            min_notional = float(symbol_specs.get("tradeMinUSDT", symbol_specs.get("minNotional", 5.0))) if symbol_specs else 5.0
            step = float(symbol_specs.get("size", symbol_specs.get("stepSize", 0.001))) if symbol_specs else 0.001
            qty = self._round_quantity(symbol, (min_notional * 1.05) / current_price, symbol_specs)
            if qty <= 0 or not self._check_min_notional(qty, current_price, symbol_specs):
                self.logger.warning(f"{symbol}: does not meet min lot (min_notional={min_notional}, price={current_price})")
                return None

        self.logger.info(f"ENTRY PREPARE {side.value} {symbol} | Qty: {qty:.6f} | Price: ~{current_price:.4f} | "
                         f"Leverage: {leverage}x | PositionSide: {position_side} | StopDist: {stop_distance_pct:.2f}%")

        # Set leverage
        try:
            lev_res = await self.client.set_leverage(bingx_symbol, leverage, position_side=position_side)
            if lev_res and not lev_res.get("error"):
                self.logger.info(f"Leverage set: {bingx_symbol} {leverage}x {position_side}")
            else:
                err = lev_res.get("msg", "unknown") if lev_res else "no response"
                self.logger.warning(f"Leverage warning {symbol}: {err} (may already be set)")
        except Exception as e:
            self.logger.warning(f"Leverage error {symbol}: {e} (continuing)")

        # Set margin mode (ignore errors)
        try:
            margin_res = await self.client.set_margin_mode(bingx_symbol, "CROSSED")
            if margin_res and margin_res.get("code") == 0:
                self.logger.info(f"Margin mode set: {bingx_symbol} CROSSED")
            else:
                self.logger.debug(f"Margin mode skipped for {symbol}")
        except Exception as e:
            self.logger.debug(f"Margin mode error {symbol}: {e} (ignoring)")

        # Calculate SL/TP
        try:
            temp_pos = Position(symbol=symbol, side=side, quantity=qty, entry_price=current_price, leverage=leverage)
            sl_price, tp_price = self.risk_manager.calculate_sl_tp(temp_pos, atr)
        except Exception as e:
            self.logger.error(f"SL/TP error {symbol}: {e}")
            return None

        # Place MARKET entry order
        order_side_str = "BUY" if side == OrderSide.BUY else "SELL"
        self.logger.info(f"PLACING ORDER: {bingx_symbol} {order_side_str} {position_side} qty={qty:.6f} MARKET")
        result = await self.client.place_order(
            symbol=bingx_symbol, side=order_side_str, position_side=position_side,
            quantity=qty, order_type="MARKET"
        )
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

        # Place STOP LOSS order
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

        # Place TAKE PROFIT order
        tp_result = await self.client.place_stop_order(
            symbol=bingx_symbol, side=sl_side, stop_price=tp_price,
            order_type="TAKE_PROFIT_MARKET", position_side=position_side, close_position=True
        )
        tp_order_id = tp_result.get("orderId", "") if tp_result and not tp_result.get("error") else ""
        if tp_order_id:
            self.logger.info(f"TP SET: {symbol} @ {tp_price:.4f} | ID: {tp_order_id}")
        else:
            self.logger.warning(f"TP NOT SET {symbol}: {tp_result.get('msg', 'unknown error')}")

        # Create position object
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
        bingx_symbol = symbol.replace("/", "-")
        close_side = "SELL" if side == OrderSide.BUY else "BUY"
        try:
            res = await self.client.close_position(
                symbol=bingx_symbol, position_side=position_side, quantity="0"
            )
            if res and not res.get("error") and res.get("orderId"):
                self.logger.info(f"Position {symbol} closed via close_position API | ID: {res.get('orderId')}")
                return True
            res = await self.client.place_order(
                symbol=bingx_symbol, side=close_side, position_side=position_side,
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
