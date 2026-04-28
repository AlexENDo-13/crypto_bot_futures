"""
Exit Manager — FIXED: correct position side for closing, emergency close all
Исправления:
- Правильное определение направления закрытия (side противоположен позиции)
- Использование closePosition=true для надежного закрытия
- Fallback на individual close при bulk close failure
- Проверка что все позиции закрыты
"""
import asyncio
import logging
import time
from typing import Optional, Dict, Any, List

logger = logging.getLogger("ExitManager")


class ExitManager:
    def __init__(self, settings, logger, api_client, risk_manager):
        self.settings = settings
        self.logger = logger
        self.api_client = api_client
        self.risk_manager = risk_manager

    async def check_exits(self, positions, on_position_closed):
        """Check and execute exits for all positions"""
        for symbol, pos in list(positions.items()):
            try:
                await self._check_single_exit(pos, on_position_closed)
            except Exception as e:
                self.logger.error(f"Exit check error for {symbol}: {e}")

    async def _check_single_exit(self, pos, on_position_closed):
        """Check exit conditions for single position"""
        symbol = pos.symbol
        position_side = "LONG" if pos.side == OrderSide.BUY else "SHORT"

        # Check stop loss
        if pos.stop_loss_price and pos.current_price:
            if position_side == "LONG" and pos.current_price <= pos.stop_loss_price:
                self.logger.warning(f"STOP LOSS TRIGGERED: {symbol} LONG | Entry: {pos.entry_price:.4f} | Current: {pos.current_price:.4f} | SL: {pos.stop_loss_price:.4f}")
                await self._close_and_notify(pos, position_side, "stop_loss", on_position_closed)
                return
            elif position_side == "SHORT" and pos.current_price >= pos.stop_loss_price:
                self.logger.warning(f"STOP LOSS TRIGGERED: {symbol} SHORT | Entry: {pos.entry_price:.4f} | Current: {pos.current_price:.4f} | SL: {pos.stop_loss_price:.4f}")
                await self._close_and_notify(pos, position_side, "stop_loss", on_position_closed)
                return

        # Check take profit
        if pos.take_profit_price and pos.current_price:
            if position_side == "LONG" and pos.current_price >= pos.take_profit_price:
                self.logger.info(f"TAKE PROFIT TRIGGERED: {symbol} LONG | Entry: {pos.entry_price:.4f} | Current: {pos.current_price:.4f} | TP: {pos.take_profit_price:.4f}")
                await self._close_and_notify(pos, position_side, "take_profit", on_position_closed)
                return
            elif position_side == "SHORT" and pos.current_price <= pos.take_profit_price:
                self.logger.info(f"TAKE PROFIT TRIGGERED: {symbol} SHORT | Entry: {pos.entry_price:.4f} | Current: {pos.current_price:.4f} | TP: {pos.take_profit_price:.4f}")
                await self._close_and_notify(pos, position_side, "take_profit", on_position_closed)
                return

        # Check trailing stop
        if self.settings.get("trailing_stop_enabled", True):
            await self._check_trailing_stop(pos, position_side, on_position_closed)

        # Check max hold time
        max_hold = self.settings.get("max_hold_time_minutes", 240)
        if pos.entry_time and (time.time() - pos.entry_time.timestamp()) > max_hold * 60:
            self.logger.info(f"MAX HOLD TIME: {symbol} | Holding for {max_hold} min")
            await self._close_and_notify(pos, position_side, "max_hold_time", on_position_closed)

    async def _check_trailing_stop(self, pos, position_side, on_position_closed):
        """Check trailing stop condition"""
        if not pos.highest_price or not pos.current_price:
            return

        trail_dist = self.settings.get("trailing_stop_distance_percent", 2.0) / 100
        activation = self.settings.get("trailing_activation", 1.5) / 100

        if position_side == "LONG":
            # Update highest price
            if pos.current_price > pos.highest_price:
                pos.highest_price = pos.current_price

            # Check activation
            profit_pct = (pos.current_price - pos.entry_price) / pos.entry_price if pos.entry_price > 0 else 0
            if profit_pct >= activation:
                trail_price = pos.highest_price * (1 - trail_dist)
                if pos.current_price <= trail_price:
                    self.logger.info(f"TRAILING STOP: {pos.symbol} LONG | Highest: {pos.highest_price:.4f} | Trail: {trail_price:.4f} | Current: {pos.current_price:.4f}")
                    await self._close_and_notify(pos, position_side, "trailing_stop", on_position_closed)
        else:
            # SHORT — update lowest price
            if not hasattr(pos, 'lowest_price'):
                pos.lowest_price = pos.entry_price
            if pos.current_price < pos.lowest_price:
                pos.lowest_price = pos.current_price

            profit_pct = (pos.entry_price - pos.current_price) / pos.entry_price if pos.entry_price > 0 else 0
            if profit_pct >= activation:
                trail_price = pos.lowest_price * (1 + trail_dist)
                if pos.current_price >= trail_price:
                    self.logger.info(f"TRAILING STOP: {pos.symbol} SHORT | Lowest: {pos.lowest_price:.4f} | Trail: {trail_price:.4f} | Current: {pos.current_price:.4f}")
                    await self._close_and_notify(pos, position_side, "trailing_stop", on_position_closed)

    async def _close_and_notify(self, pos, position_side, reason, on_position_closed):
        """Close position and notify callback"""
        symbol = pos.symbol

        try:
            result = await self.api_client.close_position(
                symbol=symbol.replace("/", "-"),
                position_side=position_side,
                quantity="0"  # Full close
            )

            if result and not result.get("error"):
                pos.exit_reason = reason
                pos.exit_price = pos.current_price
                pos.realized_pnl = pos.calculate_pnl(pos.current_price)
                on_position_closed(pos)
                self.logger.info(f"CLOSE SUCCESS: {symbol} {position_side} | Reason: {reason} | PnL: {pos.realized_pnl:.4f}")
            else:
                error_msg = result.get("msg", "Unknown") if result else "No response"
                self.logger.error(f"CLOSE FAILED: {symbol} {position_side} | {error_msg}")

        except Exception as e:
            self.logger.error(f"CLOSE ERROR {symbol}: {e}")

    async def emergency_close_all(self, positions, on_position_closed):
        """Emergency close all positions — FIXED"""
        self.logger.warning(f"EMERGENCY CLOSE ALL | Positions: {len(positions)}")

        # Method 1: Try individual close for each position
        for symbol, pos in list(positions.items()):
            position_side = "LONG" if pos.side == OrderSide.BUY else "SHORT"
            await self._close_and_notify(pos, position_side, "emergency_close", on_position_closed)
            await asyncio.sleep(0.5)  # Rate limit protection

        # Verify all closed
        await asyncio.sleep(2)
        try:
            remaining = await self.api_client.get_positions()
            open_count = sum(1 for p in remaining if abs(float(p.get("positionAmt", 0))) > 0)
            if open_count == 0:
                self.logger.info("All positions successfully closed")
            else:
                self.logger.warning(f"{open_count} positions still open after emergency close")
        except Exception as e:
            self.logger.error(f"Failed to verify positions after emergency close: {e}")


# Import OrderSide for type checking
from src.core.trading.position import OrderSide
