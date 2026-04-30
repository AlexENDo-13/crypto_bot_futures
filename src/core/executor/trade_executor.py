"""
Trade Executor — FIXED: await get_symbol_specs, position side handling, order confirmation.
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from src.core.trading.position import Position, OrderSide

logger = logging.getLogger("TradeExecutor")

class TradeExecutor:
    def __init__(self, settings, logger, order_manager, risk_manager, risk_controller):
        self.settings = settings
        self.logger = logger
        self.order_manager = order_manager
        self.risk_manager = risk_manager
        self.risk_controller = risk_controller

    async def execute_trade_async(self, candidate, balance, open_positions,
                                  trailing_enabled=True, trailing_distance=2.0,
                                  telegram=None, daily_pnl=0, weekly_pnl=0,
                                  start_balance=0):
        """Execute trade entry — FIXED with await for get_symbol_specs"""
        symbol = candidate.get("symbol", "")
        ind = candidate.get("indicators", {})
        signal_direction = ind.get("signal_direction", "")
        entry_type = ind.get("entry_type", "mixed")
        current_price = candidate.get("current_price", 0)

        if not symbol or not signal_direction or current_price <= 0:
            self.logger.warning(f"Invalid candidate: {symbol} {signal_direction} price={current_price}")
            return None

        if signal_direction == "LONG":
            side = "BUY"
            position_side = "LONG"
            order_side = OrderSide.BUY
        elif signal_direction == "SHORT":
            side = "SELL"
            position_side = "SHORT"
            order_side = OrderSide.SELL
        else:
            self.logger.warning(f"Invalid signal_direction: {signal_direction}")
            return None

        symbol_formatted = symbol.replace("/", "-")
        if not symbol_formatted.endswith("-USDT"):
            symbol_formatted = f"{symbol_formatted}-USDT"

        # FIX: await the coroutine!
        specs = None
        try:
            specs = await self.order_manager.api_client.get_symbol_specs(symbol_formatted)
            self.logger.debug(f"Symbol specs for {symbol_formatted}: {specs}")
        except Exception as e:
            self.logger.warning(f"Failed to get symbol specs: {e}")

        atr_percent = ind.get("atr_percent", 0.5)
        stop_distance = max(atr_percent * 1.5, 0.3)
        leverage = min(self.risk_manager.max_leverage, 10)

        quantity = self.risk_manager.calculate_position_size(
            symbol=symbol, balance=balance, risk_percent=self.risk_manager.risk_per_trade,
            stop_distance_pct=stop_distance, leverage=leverage,
            atr=current_price * (atr_percent / 100), current_price=current_price,
            symbol_specs=specs
        )

        if quantity <= 0:
            self.logger.warning(f"Quantity=0 for {symbol}, skipping")
            return None

        sl_price, tp_price = self.risk_manager.calculate_sl_tp(
            Position(symbol=symbol, side=order_side, quantity=quantity, entry_price=current_price, leverage=leverage)
        )

        self.logger.info(f"ENTRY PREPARE {side} {symbol} | Qty: {quantity:.6f} | Price: ~{current_price:.4f} | "
                         f"Leverage: {leverage}x | PositionSide: {position_side} | StopDist: {stop_distance:.2f}%")

        try:
            await self.order_manager.api_client.set_leverage(symbol_formatted, leverage, position_side)

            order_result = await self.order_manager.api_client.place_order(
                symbol=symbol_formatted,
                side=side,
                order_type="MARKET",
                quantity=quantity
            )

            if order_result and not order_result.get("error"):
                order_id = order_result.get("orderId")
                self.logger.info(f"ENTRY SUCCESS {symbol} | OrderID: {order_id} | Status: {order_result.get('status', 'UNKNOWN')}")

                pos = Position(
                    symbol=symbol,
                    side=order_side,
                    quantity=quantity,
                    entry_price=current_price,
                    leverage=leverage
                )
                pos.stop_loss_price = sl_price
                pos.take_profit_price = tp_price
                pos.strategy = entry_type
                pos.order_id = order_id
                return pos
            else:
                self.logger.warning(f"ENTRY: Order returned error/None for {symbol}, checking positions...")
                await asyncio.sleep(1.5)

                positions = await self.order_manager.api_client.get_positions(symbol_formatted)
                for pos_data in positions:
                    pos_side = pos_data.get("positionSide", "")
                    pos_amt = float(pos_data.get("positionAmt", 0))

                    if pos_side == position_side and abs(pos_amt) > 0:
                        actual_entry = float(pos_data.get("avgPrice", pos_data.get("entryPrice", current_price)))
                        self.logger.info(f"ENTRY CONFIRMED via position check: {symbol} {position_side} amt={pos_amt} entry={actual_entry}")

                        pos = Position(
                            symbol=symbol,
                            side=order_side,
                            quantity=abs(pos_amt),
                            entry_price=actual_entry,
                            leverage=leverage
                        )
                        pos.stop_loss_price = sl_price
                        pos.take_profit_price = tp_price
                        pos.strategy = entry_type
                        pos.order_id = "POSITION_CONFIRMED"
                        return pos

                error_msg = order_result.get("msg", "Unknown error") if order_result else "No response"
                self.logger.error(f"ENTRY FAILED {symbol}: {error_msg}")
                return None

        except Exception as e:
            self.logger.error(f"ENTRY ERROR {symbol}: {e}")
            return None

    async def close_position_async(self, symbol, position_side, quantity=None):
        """Close position — FIXED with proper side/positionSide"""
        symbol_formatted = symbol.replace("/", "-")
        if not symbol_formatted.endswith("-USDT"):
            symbol_formatted = f"{symbol_formatted}-USDT"

        self.logger.info(f"CLOSE REQUEST: {symbol} {position_side} | Qty: {quantity}")

        try:
            if quantity and quantity > 0:
                result = await self.order_manager.api_client.close_position(
                    symbol=symbol_formatted,
                    position_side=position_side
                )
            else:
                result = await self.order_manager.api_client.close_position(
                    symbol=symbol_formatted,
                    position_side=position_side
                )

            if result and not result.get("error"):
                self.logger.info(f"CLOSE SUCCESS {symbol} {position_side} | OrderID: {result.get('orderId')}")
                return True
            else:
                error_msg = result.get("msg", "Unknown") if result else "No response"
                self.logger.error(f"CLOSE FAILED {symbol}: {error_msg}")
                return False

        except Exception as e:
            self.logger.error(f"CLOSE ERROR {symbol}: {e}")
            return False
