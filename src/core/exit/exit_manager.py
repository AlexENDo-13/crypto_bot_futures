#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExitManager — менеджер выходов из позиций.
"""
import asyncio
import time
from typing import Dict, Callable
from datetime import datetime

from src.config.settings import Settings
from src.core.logger import BotLogger
from src.core.trading.position import Position, ExitReason

class ExitManager:
    def __init__(self, settings: Settings, logger: BotLogger, client, risk_manager):
        self.settings = settings
        self.logger = logger
        self.client = client
        self.risk_manager = risk_manager
        self.trailing_enabled = settings.get("trailing_stop_enabled", True)
        self.trailing_distance = float(settings.get("trailing_stop_distance_percent", 2.0))
        self.trailing_activation = float(settings.get("trailing_activation", 1.5))
        self.max_hold_time = float(settings.get("max_hold_time_minutes", 240))
        self.dead_weight_enabled = settings.get("dead_weight_exit_enabled", True)

    async def check_exits(self, positions: Dict[str, Position], on_close: Callable = None):
        for symbol, pos in list(positions.items()):
            if pos.closed:
                continue
            try:
                ticker = await self.client.get_ticker(symbol.replace("/", "-"))
                if not ticker:
                    continue
                current_price = ticker.get("markPrice", ticker.get("lastPrice", 0))
                if current_price <= 0:
                    continue

                pos.update_market_price(current_price)
                pnl_pct = pos.calculate_pnl_percent()
                hold_time = (datetime.utcnow() - pos.entry_time).total_seconds() / 60 if pos.entry_time else 0

                # 1. Stop Loss
                if pos.stop_loss_price > 0:
                    if (pos.side.value == "BUY" and current_price <= pos.stop_loss_price) or \
                       (pos.side.value == "SELL" and current_price >= pos.stop_loss_price):
                        await self._close_position(pos, current_price, ExitReason.STOP_LOSS, positions, on_close)
                        continue

                # 2. Take Profit
                if pos.take_profit_price > 0:
                    if (pos.side.value == "BUY" and current_price >= pos.take_profit_price) or \
                       (pos.side.value == "SELL" and current_price <= pos.take_profit_price):
                        await self._close_position(pos, current_price, ExitReason.TAKE_PROFIT, positions, on_close)
                        continue

                # 3. Trailing Stop
                if self.trailing_enabled and pnl_pct >= self.trailing_activation:
                    if pos.side.value == "BUY":
                        trail_price = pos.max_price_seen * (1 - self.trailing_distance / 100)
                        if current_price <= trail_price:
                            await self._close_position(pos, current_price, ExitReason.TRAILING_STOP, positions, on_close)
                            continue
                    else:
                        trail_price = pos.min_price_seen * (1 + self.trailing_distance / 100)
                        if current_price >= trail_price:
                            await self._close_position(pos, current_price, ExitReason.TRAILING_STOP, positions, on_close)
                            continue

                # 4. Time Exit
                if self.max_hold_time > 0 and hold_time >= self.max_hold_time:
                    await self._close_position(pos, current_price, ExitReason.TIME_EXIT, positions, on_close)
                    continue

                # 5. Dead weight
                if self.dead_weight_enabled and hold_time > self.max_hold_time * 0.75 and abs(pnl_pct) < 0.5:
                    await self._close_position(pos, current_price, ExitReason.TIME_EXIT, positions, on_close)
                    continue

            except Exception as e:
                self.logger.error(f"Ошибка проверки выхода {symbol}: {e}")

    async def _close_position(self, pos: Position, exit_price: float, reason: ExitReason, positions: Dict[str, Position], on_close: Callable = None):
        try:
            bingx_symbol = pos.symbol.replace("/", "-")
            close_side = "SELL" if pos.side.value == "BUY" else "BUY"
            result = await self.client.place_order(
                symbol=bingx_symbol, side=close_side, quantity=pos.quantity,
                order_type="MARKET", position_side="BOTH"
            )
            if result and not result.get("error") and result.get("orderId"):
                pos.close(exit_price, reason)
                positions.pop(pos.symbol, None)
                self.risk_manager.register_position_close(pos)
                if on_close:
                    on_close(pos)
                self.logger.info(
                    f"📤 Позиция {pos.symbol} закрыта: {reason.value} | "
                    f"Вход: {pos.entry_price:.4f} | Выход: {exit_price:.4f} | "
                    f"PnL: {pos.realized_pnl:.4f} USDT ({pos.realized_pnl_percent:.2f}%)"
                )
            else:
                err = f"[{result.get('code')}] {result.get('msg')}" if result and result.get('error') else "No orderId"
                self.logger.error(f"❌ Ошибка закрытия {pos.symbol}: {err}")
        except Exception as e:
            self.logger.error(f"❌ Ошибка закрытия позиции {pos.symbol}: {e}")
