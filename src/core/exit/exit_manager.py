#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExitManager — полноценный менеджер выходов из позиций.
SL/TP, трейлинг-стоп, dead weight exit, интеграция с order_manager.
"""
import logging
import datetime
from typing import Optional, Dict, Callable
from src.core.trading.position import Position, ExitReason
from src.config.settings import Settings

logger = logging.getLogger(__name__)


class ExitManager:
    """Менеджер выходов из позиций с полной интеграцией."""

    def __init__(
        self,
        settings: Settings,
        logger=None,
        data_fetcher=None,
        risk_manager=None,
        risk_controller=None,
        strategy_engine=None,
        order_manager=None,
        sqlite_history=None,
    ):
        self.settings = settings
        self.logger = logger or logging.getLogger(__name__)
        self.data_fetcher = data_fetcher
        self.risk_manager = risk_manager
        self.risk_controller = risk_controller
        self.strategy_engine = strategy_engine
        self.order_manager = order_manager
        self.sqlite_history = sqlite_history

    def check_exit(self, position: Position, current_price: float) -> Optional[str]:
        """Проверяет, нужно ли закрывать позицию."""
        if current_price <= 0:
            return None

        # 1. Stop-loss
        if position.side.value == "BUY":
            if position.stop_loss_price > 0 and current_price <= position.stop_loss_price:
                return ExitReason.STOP_LOSS.value
        else:
            if position.stop_loss_price > 0 and current_price >= position.stop_loss_price:
                return ExitReason.STOP_LOSS.value

        # 2. Take-profit
        if position.side.value == "BUY":
            if position.take_profit_price > 0 and current_price >= position.take_profit_price:
                return ExitReason.TAKE_PROFIT.value
        else:
            if position.take_profit_price > 0 and current_price <= position.take_profit_price:
                return ExitReason.TAKE_PROFIT.value

        # 3. Trailing stop
        trailing_exit = self._check_trailing_stop(position, current_price)
        if trailing_exit:
            return trailing_exit

        # 4. Dead weight — time exit
        time_exit = self._check_time_exit(position)
        if time_exit:
            return time_exit

        return None

    def _check_trailing_stop(self, position: Position, current_price: float) -> Optional[str]:
        """Проверка трейлинг-стопа."""
        if not self.settings.get("trailing_stop_enabled", False):
            return None

        activation_pct = float(self.settings.get("trailing_activation", 1.5))
        callback_pct = float(self.settings.get("trailing_callback", 0.5))

        if position.side.value == "BUY":
            profit_pct = (current_price - position.entry_price) / position.entry_price * 100
            if profit_pct >= activation_pct:
                position.max_price_seen = max(position.max_price_seen, current_price)
                callback_price = position.max_price_seen * (1 - callback_pct / 100)
                if current_price <= callback_price:
                    return f"{ExitReason.TRAILING_STOP.value} (max={position.max_price_seen:.2f})"
        else:
            profit_pct = (position.entry_price - current_price) / position.entry_price * 100
            if profit_pct >= activation_pct:
                position.min_price_seen = min(position.min_price_seen, current_price)
                callback_price = position.min_price_seen * (1 + callback_pct / 100)
                if current_price >= callback_price:
                    return f"{ExitReason.TRAILING_STOP.value} (min={position.min_price_seen:.2f})"

        return None

    def _check_time_exit(self, position: Position) -> Optional[str]:
        """Проверка временного выхода."""
        max_hold = self.settings.get("max_hold_time_minutes")
        if not max_hold:
            return None
        if position.entry_time is None:
            return None
        hold_time = (datetime.datetime.utcnow() - position.entry_time).total_seconds() / 60
        if hold_time > max_hold:
            return f"{ExitReason.TIME_EXIT.value} ({hold_time:.0f}min)"
        return None

    def update_trailing(self, position: Position, current_price: float):
        """Обновление трейлинг-стопа."""
        if position.side.value == "BUY":
            position.max_price_seen = max(position.max_price_seen, current_price)
        else:
            position.min_price_seen = min(position.min_price_seen, current_price)

    async def check_all_positions(
        self,
        open_positions: Dict[str, Position],
        get_ticker_func: Callable,
        update_balance_func: Callable,
        save_history: bool = True,
        telegram_notifier=None,
        discord_notifier=None,
        current_balance: float = 0,
    ):
        """Проверяет все позиции и закрывает при необходимости."""
        for symbol, pos in list(open_positions.items()):
            try:
                # Get current price
                ticker = get_ticker_func(symbol)
                if not ticker or "lastPrice" not in ticker:
                    continue

                current_price = float(ticker["lastPrice"])
                pos.update_market_price(current_price)
                self.update_trailing(pos, current_price)

                # Check exit conditions
                exit_reason = self.check_exit(pos, current_price)
                if exit_reason:
                    await self._close_position(
                        pos, current_price, exit_reason,
                        open_positions, update_balance_func,
                        telegram_notifier, discord_notifier,
                        save_history
                    )

            except Exception as e:
                self.logger.error(f"Ошибка проверки позиции {symbol}: {e}")

    async def _close_position(
        self,
        position: Position,
        exit_price: float,
        exit_reason: str,
        open_positions: Dict[str, Position],
        update_balance_func: Callable,
        telegram_notifier=None,
        discord_notifier=None,
        save_history: bool = True,
    ):
        """Закрывает позицию и обновляет статистику."""
        symbol = position.symbol

        # Close on exchange if not demo
        if self.order_manager and not self.settings.get("demo_mode", True):
            try:
                close_side = "SELL" if position.side.value == "BUY" else "BUY"
                result = await self.order_manager.client.place_order(
                    symbol=symbol.replace("/", "-"),
                    side=close_side,
                    quantity=position.quantity,
                    order_type="MARKET",
                    position_side="BOTH",
                )
                if result and result.get("avgPrice"):
                    exit_price = float(result["avgPrice"])
            except Exception as e:
                self.logger.error(f"❌ Ошибка закрытия на бирже {symbol}: {e}")

        # Calculate PnL
        position.close(exit_price, ExitReason(exit_reason.split()[0]) if " " in exit_reason else ExitReason(exit_reason))
        pnl = position.realized_pnl

        # Update balance
        if update_balance_func:
            try:
                update_balance_func(pnl, position.strategy)
            except Exception as e:
                self.logger.error(f"Ошибка обновления баланса: {e}")

        # Update risk manager
        if self.risk_manager:
            self.risk_manager.update_pnl(pnl)
            self.risk_manager.register_position_close(position)

        # Record in history
        if save_history and self.sqlite_history:
            try:
                self.sqlite_history.record_trade(position.to_dict())
            except Exception as e:
                self.logger.error(f"Ошибка записи в историю: {e}")

        # Remove from open positions
        if symbol in open_positions:
            del open_positions[symbol]

        # Notify
        emoji = "🔴" if pnl < 0 else "🟢"
        msg = (
            f"{emoji} **ПОЗИЦИЯ ЗАКРЫТА** {emoji}\n"
            f"Пара: {symbol}\n"
            f"Причина: {exit_reason}\n"
            f"Вход: {position.entry_price:.4f} | Выход: {exit_price:.4f}\n"
            f"PnL: {pnl:+.2f} USDT ({position.realized_pnl_percent:+.2f}%)"
        )

        self.logger.info(f"🏁 Закрыта позиция {symbol} | {exit_reason} | PnL: {pnl:+.2f} USDT")

        if telegram_notifier:
            try:
                telegram_notifier.send_sync(msg)
            except Exception:
                pass

        if discord_notifier:
            try:
                discord_notifier.send_sync(msg)
            except Exception:
                pass

    def record_exchange_tp_close(self, symbol: str, position: Position, current_price: float, pnl: float):
        """Регистрирует закрытие позиции на бирже (SL/TP/ручное)."""
        position.close(current_price, ExitReason.EXCHANGE_CLOSE)
        position.realized_pnl = pnl

        if self.risk_manager:
            self.risk_manager.update_pnl(pnl)
            self.risk_manager.register_position_close(position)

        if self.sqlite_history:
            try:
                self.sqlite_history.record_trade(position.to_dict())
            except Exception:
                pass

        self.logger.info(f"🏁 Позиция {symbol} закрыта на бирже | PnL: {pnl:+.2f} USDT")
