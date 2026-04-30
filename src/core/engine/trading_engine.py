"""Main trading engine orchestrator."""
import asyncio
import logging
from typing import Optional

from src.core.bot_logger import BotLogger
from src.exchange.exchange import Exchange
from src.strategies.strategy_manager import StrategyManager
from src.core.risk_manager import RiskManager
from src.core.order_manager import OrderManager
from src.core.exit_manager import ExitManager
from src.core.models import Signal, Position


class TradingEngine:
    """Основной движок торговли."""

    def __init__(self, settings, logger: BotLogger, api_client, telegram=None):
        self.settings = settings
        self.logger = logger
        self.api_client = api_client
        self.telegram = telegram

        self.running = False
        self.positions = []
        self.symbols = settings.get("symbols", ["BTC-USDT", "ETH-USDT"])
        self.timeframes = settings.get("timeframes", ["15m", "1h", "4h", "1d"])

        self.strategy_manager = StrategyManager(settings, logger)
        self.risk_manager = RiskManager(settings, logger)
        self.order_manager = OrderManager(api_client, logger)
        self.exit_manager = ExitManager(api_client, logger, settings)

    async def start(self):
        self.running = True
        self.logger.info("TradingEngine started")
        while self.running:
            try:
                await self._tick()
                await asyncio.sleep(60)
            except Exception as e:
                self.logger.error(f"Engine tick error: {e}", exc_info=True)
                await asyncio.sleep(10)

    async def stop(self):
        self.running = False
        self.logger.info("TradingEngine stopped")

    async def _tick(self):
        # Scan markets
        for symbol in self.symbols:
            try:
                signal = await self.strategy_manager.analyze(symbol, self.timeframes)
                if signal:
                    await self._process_signal(signal)
            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {e}")

        # Manage exits
        try:
            await self.exit_manager.check_exits(self.positions)
        except Exception as e:
            self.logger.error(f"Exit check error: {e}")

    async def _process_signal(self, signal: Signal):
        # Risk check
        if not self.risk_manager.can_open_position(signal, self.positions):
            self.logger.info(f"Signal rejected by risk manager: {signal.symbol}")
            return

        # Place order
        try:
            order = await self.order_manager.open_position(signal)
            if order:
                position = Position(
                    symbol=signal.symbol,
                    side=signal.side,
                    entry_price=signal.entry_price,
                    quantity=order.quantity,
                    leverage=self.settings.get("leverage", 5),
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                    order_id=order.order_id
                )
                self.positions.append(position)
                self.logger.info(f"Position opened: {position}")
        except Exception as e:
            self.logger.error(f"Failed to open position: {e}")
