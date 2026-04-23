#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TradingEngine — полностью исправленный торговый движок.
Совместимость всех компонентов, корректная работа с любыми депозитами.
"""
import asyncio
import threading
import time
import traceback
from typing import Dict, List, Optional
from datetime import datetime

from src.core.logger import BotLogger
from src.core.market.data_fetcher import DataFetcher
from src.core.trading.order_manager import OrderManager
from src.core.trading.position import Position, OrderSide, ExitReason
from src.config.constants import OrderSide as ConstOrderSide
from src.core.risk.risk_manager import RiskManager
from src.core.risk.risk_controller import RiskController
from src.intelligence.strategy_engine import StrategyEngine
from src.notifications.telegram_notifier import TelegramNotifier
from src.notifications.discord_notifier import DiscordNotifier
from src.utils.api_client import AsyncBingXClient
from src.utils.performance_metrics import PerformanceMetrics
from src.utils.sqlite_history import SQLiteTradeHistory
from src.utils.profiler import Profiler
from src.core.scanner.market_scanner import MarketScanner
from src.core.executor.trade_executor import TradeExecutor
from src.core.exit.exit_manager import ExitManager
from src.config.settings import Settings


class TradingEngine:
    """Полноценный асинхронный торговый движок."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = BotLogger(level=settings.get("log_level", "INFO"))
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()
        self._paused = False
        self._state = "STOPPED"
        self._update_callbacks: List[callable] = []

        # API Client
        self.client = AsyncBingXClient(
            api_key=settings.get("api_key", ""),
            api_secret=settings.get("api_secret", ""),
            demo_mode=settings.get("demo_mode", True),
            settings=settings.data,
        )
        self.logger.info(f"API клиент инициализирован (Demo: {settings.get('demo_mode', True)})")

        # Components
        self.profiler = Profiler(self.logger, settings.data)
        self.data_fetcher = DataFetcher(self.client, self.logger, settings.data)
        self.risk_manager = RiskManager(self.client, settings.data)
        self.order_manager = OrderManager(self.client, settings, self.logger)
        self.risk_controller = RiskController(self.logger, settings.data)
        self.strategy_engine = StrategyEngine(self.logger, settings)
        self.performance_metrics = PerformanceMetrics(self.logger, settings.data)
        self.sqlite_history = SQLiteTradeHistory()

        self.scanner = MarketScanner(
            settings, self.logger, self.data_fetcher,
            self.risk_controller, self.strategy_engine
        )
        self.executor = TradeExecutor(
            settings, self.logger, self.order_manager,
            self.risk_manager, self.risk_controller
        )
        self.exit_manager = ExitManager(
            settings=settings,
            logger=self.logger,
            data_fetcher=self.data_fetcher,
            risk_manager=self.risk_manager,
            risk_controller=self.risk_controller,
            strategy_engine=self.strategy_engine,
            order_manager=self.order_manager,
            sqlite_history=self.sqlite_history,
        )

        # Notifiers
        self.telegram = None
        if settings.get("telegram_enabled"):
            try:
                self.telegram = TelegramNotifier(
                    bot_token=settings.get("telegram_bot_token", ""),
                    chat_id=settings.get("telegram_chat_id", ""),
                    logger=self.logger,
                    commands_enabled=settings.get("telegram_commands_enabled", True),
                )
                self.telegram.set_engine(self)
            except Exception as e:
                self.logger.warning(f"Telegram не инициализирован: {e}")

        self.discord = None
        if settings.get("discord_enabled"):
            try:
                self.discord = DiscordNotifier(
                    webhook_url=settings.get("discord_webhook_url", ""),
                    logger=self.logger,
                )
            except Exception as e:
                self.logger.warning(f"Discord не инициализирован: {e}")

        # Balances
        self.balance = float(settings.get("virtual_balance", 100.0))
        self.real_balance = 0.0

        self.open_positions: Dict[str, Position] = {}
        self.last_prices: Dict[str, float] = {}

        self.scan_interval = int(settings.get("scan_interval_minutes", 5)) * 60
        self.last_scan_time = 0.0
        self.force_scan = False
        self.max_positions = int(settings.get("max_positions", 2))

        self.daily_profit_target = float(settings.get("daily_profit_target_percent", 5.0))
        self.daily_target_reached = False

        self._force_scan_event = asyncio.Event()
        self.consecutive_losses = 0
        self._last_status_update = 0

    @property
    def running(self) -> bool:
        return self._running

    def is_running(self) -> bool:
        return self._running and not self._paused

    def get_status(self) -> dict:
        """Возвращает текущий статус движка."""
        total_pnl = sum(p.unrealized_pnl for p in self.open_positions.values())
        return {
            "state": self._state,
            "running": self._running,
            "paused": self._paused,
            "balance": self.balance,
            "real_balance": self.real_balance,
            "positions": len(self.open_positions),
            "pnl": total_pnl,
            "daily_pnl": self.risk_manager.daily_pnl if hasattr(self.risk_manager, "daily_pnl") else 0,
            "consecutive_losses": self.risk_manager.consecutive_losses if hasattr(self.risk_manager, "consecutive_losses") else 0,
        }

    def set_update_callback(self, callback: callable):
        """Регистрирует callback для обновлений UI."""
        self._update_callbacks.append(callback)

    def _notify_update(self, data: dict):
        """Отправляет обновление всем подписчикам."""
        for cb in self._update_callbacks:
            try:
                cb(data)
            except Exception:
                pass

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._paused = False
        self._state = "RUNNING"
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._thread.start()
        self.logger.info("✅ Асинхронный торговый движок запущен")

    def stop(self):
        self._running = False
        self._paused = False
        self._state = "STOPPED"
        self._stop_event.set()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        try:
            self.sqlite_history.close()
        except Exception:
            pass
        self.logger.info("🛑 Торговый движок остановлен")

    def pause(self):
        self._paused = True
        self._state = "PAUSED"
        self.logger.info("⏸ Движок на паузе")

    def resume(self):
        self._paused = False
        self._state = "RUNNING"
        self.logger.info("▶ Движок возобновлён")

    def scan_now(self):
        self.force_scan = True
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._force_scan_event.set)

    def _run_async_loop(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self._loop = asyncio.get_event_loop()
        try:
            self._loop.run_until_complete(self._async_main())
        except Exception as e:
            if "Event loop stopped" not in str(e):
                self.logger.error(f"Критическая ошибка в event loop: {e}")

    async def _async_main(self):
        # Check real balance on start
        await self._update_real_balance_async()

        if not self.settings.get("demo_mode") and self.real_balance <= 0:
            self.logger.critical(
                "❌ Реальный режим включен, но баланс 0 или ключи не работают. "
                "Бот не будет торговать."
            )

        self.risk_controller.daily_start_balance = self.balance
        if hasattr(self.performance_metrics, "daily_start_balance"):
            self.performance_metrics.daily_start_balance = self.balance

        while self._running:
            try:
                if self._paused:
                    await asyncio.sleep(1)
                    continue

                await asyncio.wait_for(self._run_iteration_async(), timeout=300.0)
            except asyncio.TimeoutError:
                self.logger.error("Итерация превысила таймаут (5 мин)")
            except Exception as e:
                self.logger.error(f"Ошибка в главном цикле: {e}\n{traceback.format_exc()}")
                await asyncio.sleep(10)

    async def _run_iteration_async(self):
        self.profiler.record_system_metrics()

        # 1. Sync with exchange
        await self._sync_positions_with_exchange()
        await self._update_positions_prices_async()

        # 2. Check exits
        await self.exit_manager.check_all_positions(
            self.open_positions,
            get_ticker_func=self._sync_get_ticker,
            update_balance_func=self._update_virtual_balance_sync,
            save_history=True,
            telegram_notifier=self.telegram,
            discord_notifier=self.discord,
            current_balance=self.balance,
        )

        # 3. Check drawdown
        if self.balance > 0 and hasattr(self.performance_metrics, "daily_start_balance"):
            start_bal = self.performance_metrics.daily_start_balance
            if start_bal and start_bal > 0:
                drawdown = (self.balance - start_bal) / start_bal * 100
                if drawdown <= -20:
                    self.logger.critical(f"🚨 АВАРИЙНАЯ ОСТАНОВКА! Просадка {drawdown:.1f}%")
                    if self.telegram:
                        try:
                            self.telegram.send_sync(f"🚨 АВАРИЙНАЯ ОСТАНОВКА! Просадка {drawdown:.1f}%")
                        except Exception:
                            pass
                    await self.emergency_close_all_async()
                    self._running = False
                    return

        # 4. Market scan
        now = time.time()
        if not self.force_scan and (now - self.last_scan_time < self.scan_interval):
            await asyncio.sleep(5)
            return

        self.force_scan = False
        self.last_scan_time = now

        can_scan, reason = self.risk_controller.check_circuit_breaker(self.balance)
        if not can_scan:
            self.logger.warning(f"Сканирование пропущено: {reason}")
            return

        if len(self.open_positions) >= self.max_positions:
            return

        # Check daily target
        if self.daily_target_reached:
            return

        ignore_session = self.settings.get("force_ignore_session", False)

        self.logger.info("🔍 Запуск сканирования рынка...")
        candidates = await self.scanner.scan_async(
            self.balance,
            max_pairs=100,
            max_asset_price_ratio=0.5,
            ignore_session_check=ignore_session,
        )

        if not candidates:
            return

        for c in candidates:
            if len(self.open_positions) >= self.max_positions:
                break

            can_trade, reason = self.risk_manager.can_open_position(
                len(self.open_positions), self.balance
            )
            if not can_trade:
                self.logger.info(f"⛔ Торговля запрещена: {reason}")
                continue

            pos = await self.executor.execute_trade_async(
                c, self.balance, self.open_positions,
                self.settings.get("trailing_stop_enabled", True),
                self.settings.get("trailing_stop_distance_percent", 1.5),
                self.telegram,
                getattr(self.performance_metrics, "get_daily_pnl_percent", lambda: 0)(),
                getattr(self.performance_metrics, "get_weekly_pnl_percent", lambda: 0)(),
                getattr(self.performance_metrics, "weekly_start_balance", self.balance),
            )

            if pos:
                self.open_positions[pos.symbol] = pos
                self.risk_controller.register_position_open(pos.symbol)
                if hasattr(self.strategy_engine, "last_trade_time"):
                    self.strategy_engine.last_trade_time = time.time()
                if hasattr(self.performance_metrics, "record_trade"):
                    self.performance_metrics.record_trade(
                        pos.symbol, pos.entry_price, pos.side.value,
                        strategy=c["indicators"].get("entry_type", "unknown")
                    )

                # Notify UI
                self._notify_update({
                    "type": "new_position",
                    "data": pos.to_dict(),
                })

        # Send status update
        self._send_status_update()

    def _send_status_update(self):
        """Отправляет обновление статуса в UI."""
        now = time.time()
        if now - self._last_status_update < 5:  # Max every 5 seconds
            return
        self._last_status_update = now

        status = self.get_status()
        self._notify_update({"type": "status", "data": status})

    async def _update_real_balance_async(self):
        """Обновляет реальный баланс."""
        try:
            account = await self.client.get_account_info()
            if account and "balance" in account:
                self.real_balance = float(account["balance"])
                if not self.settings.get("demo_mode"):
                    self.balance = self.real_balance
            else:
                if not self.settings.get("demo_mode"):
                    self.logger.error(f"❌ Ошибка получения баланса: {account}")
        except Exception as e:
            if not self.settings.get("demo_mode"):
                self.logger.error(f"❌ Ошибка подключения к BingX: {e}")

    async def _sync_positions_with_exchange(self):
        """Сверяет позиции с биржей."""
        if self.settings.get("demo_mode"):
            return

        try:
            exchange_positions = await self.client.get_positions()
        except Exception as e:
            self.logger.error(f"Ошибка получения позиций с биржи: {e}")
            return

        exchange_symbols = set()
        for p in exchange_positions:
            amt = float(p.get("positionAmt", 0))
            if amt != 0:
                sym = p.get("symbol", "").replace("-USDT", "/USDT")
                exchange_symbols.add(sym)

        # Remove positions closed on exchange
        for sym in list(self.open_positions.keys()):
            if sym not in exchange_symbols:
                pos = self.open_positions[sym]
                self.logger.info(f"🏁 Позиция {sym} закрыта на бирже")
                self.exit_manager.record_exchange_tp_close(
                    sym, pos, pos.current_price, 0.0
                )
                del self.open_positions[sym]
                self.risk_controller.register_position_close(sym)

        await self._update_real_balance_async()

    async def _update_positions_prices_async(self):
        """Обновляет цены для открытых позиций."""
        if not self.open_positions:
            return

        tasks = []
        for symbol, pos in self.open_positions.items():
            tasks.append(self._fetch_price_update(symbol, pos))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _fetch_price_update(self, symbol: str, pos: Position):
        try:
            ticker = await self.client.get_ticker(symbol.replace("/", "-"))
            if ticker and "lastPrice" in ticker:
                price = float(ticker["lastPrice"])
                self.last_prices[symbol] = price
                pos.update_market_price(price)
        except Exception:
            pass

    def _sync_get_ticker(self, symbol: str) -> Dict:
        """Синхронный доступ к последней цене."""
        if symbol in self.last_prices:
            return {"lastPrice": self.last_prices[symbol]}
        return {}

    def _update_virtual_balance_sync(self, pnl: float, strategy_type: str = None):
        """Обновляет виртуальный баланс."""
        if self.settings.get("demo_mode"):
            self.balance += pnl
            self.settings.set("virtual_balance", self.balance)

        if hasattr(self.risk_controller, "add_pnl"):
            self.risk_controller.add_pnl(pnl)
        if hasattr(self.risk_manager, "update_pnl"):
            self.risk_manager.update_pnl(pnl)
        if hasattr(self.strategy_engine, "record_trade_result"):
            self.strategy_engine.record_trade_result(pnl)
        if hasattr(self.performance_metrics, "record_close"):
            self.performance_metrics.record_close(pnl, self.balance, strategy_type)

        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        # Check daily target
        if hasattr(self.performance_metrics, "daily_start_balance"):
            start = self.performance_metrics.daily_start_balance
            if start and start > 0:
                daily_pct = (self.balance - start) / start * 100
                if daily_pct >= self.daily_profit_target:
                    self.daily_target_reached = True
                    self.logger.info(f"🎯 Дневная цель достигнута: +{daily_pct:.1f}%")

    async def emergency_close_all_async(self):
        """Экстренное закрытие всех позиций."""
        self.logger.warning("🛑 ЗАПУЩЕНО ЭКСТРЕННОЕ ЗАКРЫТИЕ ПОЗИЦИЙ!")
        for sym, pos in list(self.open_positions.items()):
            try:
                success = await self.executor.close_position_async(sym, pos.side, pos.quantity)
                if success:
                    del self.open_positions[sym]
                    self.logger.info(f"✅ Экстренно закрыт {sym}")
            except Exception as e:
                self.logger.error(f"❌ Ошибка закрытия {sym}: {e}")
