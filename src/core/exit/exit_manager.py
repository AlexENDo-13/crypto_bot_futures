#!/usr/bin/env python3
import asyncio
from typing import Dict, Callable
from datetime import datetime
from src.core.trading.position import Position, ExitReason

class ExitManager:
    def __init__(self, settings, logger, client, risk_manager):
        self.settings = settings; self.logger = logger; self.client = client; self.risk_manager = risk_manager
        self.trailing_enabled = settings.get("trailing_stop_enabled", True)
        self.trailing_distance = float(settings.get("trailing_stop_distance_percent", 2.0))
        self.trailing_activation = float(settings.get("trailing_activation", 1.5))
        self.max_hold_time = float(settings.get("max_hold_time_minutes", 240))
        self.dead_weight_enabled = settings.get("dead_weight_exit_enabled", True)
        self.partial_close = settings.get("partial_close_enabled", True)
        self.partial_at_tp1 = float(settings.get("partial_close_at_tp1", 0.50))
        self.partial_at_tp2 = float(settings.get("partial_close_at_tp2", 0.30))
        self.breakeven_after_tp1 = settings.get("breakeven_after_tp1", True)
        self.dynamic_sl = settings.get("dynamic_sl_enabled", True)
        self.dynamic_tp = settings.get("dynamic_tp_enabled", True)

    async def check_exits(self, positions, on_close=None):
        for symbol, pos in list(positions.items()):
            if pos.closed: continue
            try:
                ticker = await self.client.get_ticker(symbol.replace("/", "-"))
                if not ticker: continue
                current_price = ticker.get("markPrice", ticker.get("lastPrice", 0))
                if current_price <= 0: continue
                pos.update_market_price(current_price)
                pnl_pct = pos.calculate_pnl_percent()
                hold_time = (datetime.utcnow() - pos.entry_time).total_seconds() / 60 if pos.entry_time else 0
                if self.partial_close and not pos.partial_closes:
                    tp_distance = abs(pos.take_profit_price - pos.entry_price)
                    if tp_distance > 0:
                        progress = abs(current_price - pos.entry_price) / tp_distance
                        if progress >= 0.5:
                            pnl = pos.partial_close(self.partial_at_tp1, current_price)
                            self.logger.info(f"✂️ Частичное закрытие {symbol}: {self.partial_at_tp1*100:.0f}% | PnL: {pnl:.4f}")
                            if self.breakeven_after_tp1:
                                if pos.move_to_breakeven():
                                    self.logger.info(f"🛡️ SL {symbol} перемещён на безубыток")
                                    try:
                                        await self.client.cancel_all_orders(symbol.replace("/", "-"))
                                        sl_side = "SELL" if pos.side.value == "BUY" else "BUY"
                                        await self.client.place_stop_order(symbol=symbol.replace("/", "-"), side=sl_side, stop_price=pos.entry_price, order_type="STOP_MARKET", position_side="BOTH", close_position=True)
                                    except Exception as e: self.logger.warning(f"⚠️ Не удалось обновить SL {symbol}: {e}")
                if self.partial_close and len(pos.partial_closes) == 1:
                    tp_distance = abs(pos.take_profit_price - pos.entry_price)
                    if tp_distance > 0:
                        progress = abs(current_price - pos.entry_price) / tp_distance
                        if progress >= 0.8:
                            pnl = pos.partial_close(self.partial_at_tp2, current_price)
                            self.logger.info(f"✂️ Частичное закрытие {symbol}: {self.partial_at_tp2*100:.0f}% | PnL: {pnl:.4f}")
                if self.trailing_enabled and pnl_pct >= self.trailing_activation:
                    pos.trailing_activated = True; pos.update_trailing_stop(self.trailing_distance)
                if pos.stop_loss_price > 0:
                    if (pos.side.value == "BUY" and current_price <= pos.stop_loss_price) or (pos.side.value == "SELL" and current_price >= pos.stop_loss_price):
                        await self._close_position(pos, current_price, ExitReason.STOP_LOSS, positions, on_close); continue
                if pos.take_profit_price > 0:
                    if (pos.side.value == "BUY" and current_price >= pos.take_profit_price) or (pos.side.value == "SELL" and current_price <= pos.take_profit_price):
                        await self._close_position(pos, current_price, ExitReason.TAKE_PROFIT, positions, on_close); continue
                if self.trailing_enabled and pos.trailing_activated and pos.trailing_stop_price > 0:
                    if pos.side.value == "BUY" and current_price <= pos.trailing_stop_price:
                        await self._close_position(pos, current_price, ExitReason.TRAILING_STOP, positions, on_close); continue
                    elif pos.side.value == "SELL" and current_price >= pos.trailing_stop_price:
                        await self._close_position(pos, current_price, ExitReason.TRAILING_STOP, positions, on_close); continue
                if self.max_hold_time > 0 and hold_time >= self.max_hold_time:
                    await self._close_position(pos, current_price, ExitReason.TIME_EXIT, positions, on_close); continue
                if self.dead_weight_enabled and hold_time > self.max_hold_time * 0.75 and abs(pnl_pct) < 0.3:
                    await self._close_position(pos, current_price, ExitReason.TIME_EXIT, positions, on_close); continue
            except Exception as e: self.logger.error(f"Ошибка проверки выхода {symbol}: {e}")

    async def _close_position(self, pos, exit_price, reason, positions, on_close=None):
        try:
            bingx_symbol = pos.symbol.replace("/", "-")
            try: await self.client.cancel_all_orders(bingx_symbol)
            except Exception: pass
            close_side = "SELL" if pos.side.value == "BUY" else "BUY"
            result = await self.client.place_order(symbol=bingx_symbol, side=close_side, quantity=pos.quantity, order_type="MARKET", position_side="BOTH")
            if result and not result.get("error") and result.get("orderId"):
                pos.close(exit_price, reason); positions.pop(pos.symbol, None)
                self.risk_manager.register_position_close(pos)
                if on_close: on_close(pos)
                self.logger.info(f"📤 Позиция {pos.symbol} закрыта: {reason.value} | Вход: {pos.entry_price:.4f} | Выход: {exit_price:.4f} | PnL: {pos.realized_pnl:.4f} ({pos.realized_pnl_percent:.2f}%)")
            else:
                err = f"[{result.get('code')}] {result.get('msg')}" if result and result.get('error') else "No orderId"
                self.logger.error(f"❌ Ошибка закрытия {pos.symbol}: {err}")
        except Exception as e: self.logger.error(f"❌ Ошибка закрытия позиции {pos.symbol}: {e}")
